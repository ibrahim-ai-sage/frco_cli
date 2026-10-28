"""Recherche paginée de comptes selon des critères GTM."""

from dataclasses import dataclass
import re
import unicodedata
from typing import Any

from frco.clients.api_gouv_client import ApiGouvClient
from frco.models.company import Company
from frco.services.activity_reference import resolve_naf_codes
from frco.services.company_service import CompanyDataError, CompanyService


PAGE_SIZE = 25
API_RESULT_CAP = 10_000
COMMUNE_CODE = re.compile(r"(?:[0-9]{2}|2A|2B)[0-9]{3}", re.IGNORECASE)
EMPLOYEE_BAND_RANGES: dict[str, tuple[int, int | None]] = {
    "00": (0, 0), "01": (1, 2), "02": (3, 5), "03": (6, 9),
    "11": (10, 19), "12": (20, 49), "21": (50, 99), "22": (100, 199),
    "31": (200, 249), "32": (250, 499), "41": (500, 999),
    "42": (1000, 1999), "51": (2000, 4999), "52": (5000, 9999),
    "53": (10000, None),
}


class ProspectListError(Exception):
    """Signale des filtres invalides ou une recherche non exhaustive."""


@dataclass(frozen=True)
class ProspectFilters:
    """Critères d'une liste de prospection."""

    naf: str
    region: str | None = None
    department: str | None = None
    city: str | None = None
    employees_min: int | None = None
    employees_max: int | None = None
    revenue_min: int | None = None
    revenue_max: int | None = None
    multi_site_only: bool = False
    establishments_min: int | None = None
    establishments_max: int | None = None
    active_only: bool = False


class ProspectListService:
    """Collecte et normalise tous les résultats accessibles d'une recherche."""

    def __init__(self, client: ApiGouvClient) -> None:
        """Initialise le service avec un client HTTP.

        Args:
            client: Client de l'API Recherche d'entreprises.
        """
        self.client = client
        self.company_service = CompanyService(client)

    def build(self, filters: ProspectFilters) -> list[Company]:
        """Construit une liste complète ou échoue sans résultat partiel.

        Args:
            filters: Critères NAF et GTM.

        Returns:
            Entreprises uniques, normalisées avec le modèle de ``company``.

        Raises:
            ProspectListError: Critères invalides, plafond API ou pagination incohérente.
            CompanyDataError: Données d'entreprise invalides.
        """
        _validate_filters(filters)
        try:
            naf_codes = resolve_naf_codes(filters.naf)
        except ValueError as exc:
            raise ProspectListError(str(exc)) from exc

        employee_codes = _matching_employee_codes(filters)
        if employee_codes == ():
            return []

        api_filters: dict[str, str | int] = {
            "activite_principale": ",".join(naf_codes),
        }
        if filters.region:
            api_filters["region"] = filters.region
        if filters.department:
            api_filters["departement"] = filters.department
        if filters.city:
            if COMMUNE_CODE.fullmatch(filters.city):
                api_filters["code_commune"] = filters.city.upper()
            else:
                api_filters["q"] = filters.city
                api_filters["limite_matching_etablissements"] = 100
        if employee_codes is not None:
            api_filters["tranche_effectif_salarie"] = ",".join(employee_codes)
        if filters.revenue_min is not None:
            api_filters["ca_min"] = filters.revenue_min
        if filters.revenue_max is not None:
            api_filters["ca_max"] = filters.revenue_max
        if filters.active_only:
            api_filters["etat_administratif"] = "A"

        first = self.client.search_companies(api_filters, page=1, per_page=PAGE_SIZE)
        total, pages = _page_metadata(first, expected_page=1)
        if total >= API_RESULT_CAP:
            raise ProspectListError(
                "L'API plafonne cette recherche à 10 000 résultats. "
                "Ajoutez des filtres géographiques, d'effectif ou de CA pour obtenir une liste complète."
            )

        companies: list[Company] = []
        seen: set[str] = set()
        for page_number in range(1, pages + 1):
            payload = (
                first if page_number == 1
                else self.client.search_companies(api_filters, page=page_number, per_page=PAGE_SIZE)
            )
            page_total, page_count = _page_metadata(payload, expected_page=page_number)
            if page_total != total or page_count != pages:
                raise ProspectListError("La pagination de l'API a changé pendant la recherche.")
            results = payload.get("results")
            if not isinstance(results, list) or (not results and total > 0):
                raise ProspectListError("Une page de résultats de l'API est vide ou invalide.")
            for raw in results:
                if not isinstance(raw, dict):
                    raise CompanyDataError("Un résultat de l'API est invalide.")
                siren = raw.get("siren")
                if not isinstance(siren, str) or not siren:
                    raise CompanyDataError("Un résultat ne contient pas de SIREN valide.")
                if siren in seen:
                    raise ProspectListError("Un SIREN apparaît sur plusieurs pages de l'API.")
                seen.add(siren)
                company = self.company_service.from_result(raw)
                if company.naf_code not in naf_codes:
                    raise ProspectListError("L'API a retourné une entreprise hors des codes NAF demandés.")
                if _matches_filters(company, raw, filters):
                    companies.append(company)
        if len(seen) != total:
            raise ProspectListError(
                "Le nombre d'entreprises récupérées diffère du total annoncé par l'API."
            )
        return companies


def _page_metadata(payload: dict[str, Any], *, expected_page: int) -> tuple[int, int]:
    """Valide les compteurs de pagination d'une réponse API."""
    total = payload.get("total_results")
    pages = payload.get("total_pages")
    page = payload.get("page")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (total, pages, page)):
        raise ProspectListError("Les métadonnées de pagination de l'API sont invalides.")
    if total < 0 or pages < 0 or page != expected_page:
        raise ProspectListError("Les métadonnées de pagination de l'API sont incohérentes.")
    if pages != (total + PAGE_SIZE - 1) // PAGE_SIZE:
        raise ProspectListError("Le nombre de pages annoncé par l'API est incohérent.")
    return total, pages


def _validate_filters(filters: ProspectFilters) -> None:
    """Valide les seuils numériques fournis par l'utilisateur."""
    for label, value in (
        ("employees_min", filters.employees_min),
        ("employees_max", filters.employees_max),
        ("revenue_min", filters.revenue_min),
        ("revenue_max", filters.revenue_max),
        ("establishments_min", filters.establishments_min),
        ("establishments_max", filters.establishments_max),
    ):
        if value is not None and value < 0:
            raise ProspectListError(f"{label} doit être positif ou nul.")
    for label, minimum, maximum in (
        ("effectifs", filters.employees_min, filters.employees_max),
        ("chiffre d'affaires", filters.revenue_min, filters.revenue_max),
        ("établissements", filters.establishments_min, filters.establishments_max),
    ):
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ProspectListError(f"Le minimum de {label} dépasse le maximum.")
    if filters.city is not None and not filters.city.strip():
        raise ProspectListError("La ville ne peut pas être vide.")


def _matching_employee_codes(filters: ProspectFilters) -> tuple[str, ...] | None:
    """Sélectionne les tranches entièrement contenues dans l'intervalle demandé."""
    if filters.employees_min is None and filters.employees_max is None:
        return None
    return tuple(
        code for code, (lower, upper) in EMPLOYEE_BAND_RANGES.items()
        if (filters.employees_min is None or lower >= filters.employees_min)
        and (filters.employees_max is None or (upper is not None and upper <= filters.employees_max))
    )


def _matches_filters(company: Company, raw: dict[str, Any], filters: ProspectFilters) -> bool:
    """Applique les critères qui nécessitent les données métier normalisées."""
    if filters.active_only and (
        company.administrative_status is None or company.administrative_status.code != "A"
    ):
        return False
    if filters.multi_site_only and company.company_structure.is_multi_site is not True:
        return False
    total = company.company_structure.total_establishments
    if filters.establishments_min is not None and (total is None or total < filters.establishments_min):
        return False
    if filters.establishments_max is not None and (total is None or total > filters.establishments_max):
        return False
    if filters.employees_min is not None or filters.employees_max is not None:
        band = company.employee_band
        if band is None or band.code not in _matching_employee_codes(filters):
            return False
    if filters.revenue_min is not None or filters.revenue_max is not None:
        latest = company.revenue_history[0].revenue_eur if company.revenue_history else None
        if latest is None:
            return False
        if filters.revenue_min is not None and latest < filters.revenue_min:
            return False
        if filters.revenue_max is not None and latest > filters.revenue_max:
            return False
    if filters.city and not COMMUNE_CODE.fullmatch(filters.city):
        return _city_matches(raw, filters.city)
    return True


def _city_matches(raw: dict[str, Any], city: str) -> bool:
    """Vérifie qu'un établissement retourné appartient à la ville saisie."""
    expected = _normalize_city(city)
    locations = [raw.get("siege"), *(raw.get("matching_etablissements") or [])]
    for location in locations:
        if not isinstance(location, dict):
            continue
        name = location.get("libelle_commune")
        if isinstance(name, str):
            actual = _normalize_city(name)
            if actual == expected or (
                expected in {"PARIS", "LYON", "MARSEILLE"}
                and actual.startswith(expected + " ")
            ):
                return True
    return False


def _normalize_city(value: str) -> str:
    """Compare les libellés de commune sans accents ni différences de casse."""
    decomposed = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(plain.upper().replace("-", " ").split())
