"""Sélection et normalisation du premier résultat d'entreprise."""

from datetime import datetime, timezone
import math
from typing import Any

from frco.clients.api_gouv_client import ApiGouvClient
from frco.models.company import (
    AdministrativeStatus, Company, CompanyStructure, EmployeeBand,
    Establishment, EstablishmentEntry, Metadata,
    Representative, RepresentativeCategory, RevenueExercise, RevenueGrowth,
)
from frco.services.activity_reference import naf_label, section_label


class CompanyNotFoundError(Exception):
    """Signale qu'aucune entreprise ne correspond à la recherche."""


class CompanyDataError(Exception):
    """Signale une structure de réponse API inattendue."""


SOURCE_NAME = "API Recherche d'entreprises"
ADMINISTRATIVE_STATUS_LABELS = {"A": "Active", "C": "Cessée"}
ESTABLISHMENT_STATUS_LABELS = {"A": "Actif", "F": "Fermé"}
ESTABLISHMENT_PAGE_LIMIT = 100
EMPLOYEE_BAND_LABELS = {
    "NN": "Effectif inconnu", "00": "Effectif nul", "01": "1 à 2 salariés",
    "02": "3 à 5 salariés", "03": "6 à 9 salariés", "11": "10 à 19 salariés",
    "12": "20 à 49 salariés", "21": "50 à 99 salariés", "22": "100 à 199 salariés",
    "31": "200 à 249 salariés", "32": "250 à 499 salariés",
    "41": "500 à 999 salariés", "42": "1 000 à 1 999 salariés",
    "51": "2 000 à 4 999 salariés", "52": "5 000 à 9 999 salariés",
    "53": "10 000 salariés et plus",
}
LEADER_ROLES = (
    "président", "présidente", "directeur général", "directrice générale",
    "gérant", "gérante", "administrateur", "administratrice",
    "membre du directoire",
)


class CompanyService:
    """Convertit le premier résultat de recherche en objet métier."""

    def __init__(self, client: ApiGouvClient) -> None:
        """Initialise le service.

        Args:
            client: Client chargé de la recherche HTTP.
        """
        self.client = client

    def find_first(self, query: str, *, include_establishments: bool = False) -> Company:
        """Retourne la première fiche correspondant à une requête inchangée.

        Args:
            query: Valeur transmise telle quelle à l'API.
            include_establishments: Demande le détail disponible du réseau.

        Returns:
            Première fiche normalisée.

        Raises:
            CompanyNotFoundError: Aucun résultat trouvé.
            CompanyDataError: Réponse de structure inattendue.
        """
        payload = (
            self.client.search(query, establishment_limit=ESTABLISHMENT_PAGE_LIMIT)
            if include_establishments else self.client.search(query)
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise CompanyDataError("La réponse de l'API ne contient pas de liste de résultats.")
        if not results:
            raise CompanyNotFoundError(f"Aucune entreprise trouvée pour {query!r}.")

        return self.from_result(
            results[0], query=query, include_establishments=include_establishments
        )

    def from_result(
        self,
        first: dict[str, Any],
        *,
        query: str = "",
        include_establishments: bool = False,
    ) -> Company:
        """Normalise un résultat API avec le même schéma que ``frco company``.

        Args:
            first: Résultat d'une unité légale renvoyé par l'API.
            query: Requête d'origine, pour identifier un SIRET recherché.
            include_establishments: Inclut la liste d'établissements disponible.

        Returns:
            Fiche d'entreprise homogène.

        Raises:
            CompanyDataError: Résultat de structure inattendue.
        """
        if not isinstance(first, dict):
            raise CompanyDataError("Le premier résultat de l'API est invalide.")
        raw_siege = first.get("siege")
        if raw_siege is not None and not isinstance(raw_siege, dict):
            raise CompanyDataError("Le siège du premier résultat est invalide.")
        headquarters = (
            _establishment(raw_siege)
            if raw_siege and raw_siege.get("est_siege") is not False
            else None
        )
        history = _revenue_history(first)
        naf_code = _optional_text(first, "activite_principale")
        section = _optional_text(first, "section_activite_principale")
        api_naf_label = _optional_text(first, "libelle_activite_principale")
        try:
            resolved_naf_label = api_naf_label or naf_label(naf_code)
            resolved_section_label = section_label(section)
        except (OSError, KeyError) as exc:
            raise CompanyDataError("La référence NAF locale est inaccessible ou invalide.") from exc

        status_code = _optional_text(first, "etat_administratif")
        structure = self._company_structure(
            first, query, headquarters, include_establishments=include_establishments
        )
        retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return Company(
            name=_optional_text(first, "nom_complet"),
            siren=_optional_text(first, "siren"),
            headquarters=headquarters,
            searched_establishment=_searched_establishment(first, query, headquarters),
            company_structure=structure,
            administrative_status=(
                AdministrativeStatus(status_code, ADMINISTRATIVE_STATUS_LABELS.get(status_code))
                if status_code is not None else None
            ),
            naf_code=naf_code,
            naf_label=resolved_naf_label,
            activity_section=section,
            activity_section_label=resolved_section_label,
            employee_band=_employee_band(first),
            representatives=_representatives(first),
            revenue_history=history,
            revenue_growth=_revenue_growth(history),
            metadata=Metadata(source=SOURCE_NAME, retrieved_at=retrieved_at),
        )

    def _company_structure(
        self,
        company: dict[str, Any],
        query: str,
        headquarters: Establishment | None,
        *,
        include_establishments: bool,
    ) -> CompanyStructure:
        """Construit les compteurs et, sur demande, la liste vérifiée."""
        total = _optional_count(company, "nombre_etablissements")
        active = _optional_count(company, "nombre_etablissements_ouverts")
        if not include_establishments:
            return CompanyStructure(
                total_establishments=total,
                active_establishments=active,
                is_multi_site=active > 1 if active is not None else None,
                establishments=None,
                establishments_complete=None,
            )

        records = _matching_establishments(company)
        name = _optional_text(company, "nom_complet")
        siren = _optional_text(company, "siren")
        if total is not None and len(records or []) < total and name and siren and name != query:
            additional_payload = self.client.search(
                name, establishment_limit=ESTABLISHMENT_PAGE_LIMIT
            )
            additional_results = additional_payload.get("results")
            if not isinstance(additional_results, list):
                raise CompanyDataError("La réponse complémentaire de l'API est invalide.")
            for candidate in additional_results:
                if not isinstance(candidate, dict):
                    raise CompanyDataError("Un résultat complémentaire de l'API est invalide.")
                if _optional_text(candidate, "siren") == siren:
                    additional_records = _matching_establishments(candidate)
                    if additional_records is not None:
                        records = (records or []) + additional_records
                    break

        entries = _establishment_entries(records, headquarters, siren) if records is not None else None
        # page/total_pages décrivent les entreprises, pas leurs établissements.
        # Un total égal au nombre d'entrées d'une page ne prouve pas l'exhaustivité.
        return CompanyStructure(
            total_establishments=total,
            active_establishments=active,
            is_multi_site=active > 1 if active is not None else None,
            establishments=entries,
            establishments_complete=(
                False if entries is not None and total is not None and len(entries) < total
                else None
            ),
        )


def _optional_text(data: dict[str, Any], key: str) -> str | None:
    """Lit un champ textuel facultatif sans fabriquer de valeur."""
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CompanyDataError(f"Le champ {key!r} du premier résultat est invalide.")
    return value


def _optional_count(data: dict[str, Any], key: str) -> int | None:
    """Lit un compteur fourni par l'API sans transformer une absence en zéro."""
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CompanyDataError(f"Le compteur {key!r} du premier résultat est invalide.")
    return value


def _matching_establishments(company: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Distingue une liste absente d'une liste récupérée mais vide."""
    matches = company.get("matching_etablissements")
    if matches is None:
        return None
    if not isinstance(matches, list) or any(not isinstance(match, dict) for match in matches):
        raise CompanyDataError("La liste des établissements correspondants est invalide.")
    return matches


def _establishment_entries(
    records: list[dict[str, Any]], headquarters: Establishment | None, siren: str | None
) -> list[EstablishmentEntry]:
    """Garde les SIRET du même SIREN, sans doublon, dans l'ordre reçu."""
    entries: list[EstablishmentEntry] = []
    seen: set[str] = set()
    for record in records:
        siret = _optional_text(record, "siret")
        if siret is None or siret in seen or (siren is not None and siret[:9] != siren):
            continue
        seen.add(siret)
        status_code = _optional_text(record, "etat_administratif")
        source_headquarters = record.get("est_siege")
        if source_headquarters is not None and not isinstance(source_headquarters, bool):
            raise CompanyDataError("L'indicateur de siège d'un établissement est invalide.")
        if headquarters is None or headquarters.siret is None:
            is_headquarters = source_headquarters
        else:
            verified_headquarters = siret == headquarters.siret
            is_headquarters = (
                verified_headquarters
                if source_headquarters is None or source_headquarters == verified_headquarters
                else None
            )
        entries.append(EstablishmentEntry(
            siret=siret,
            administrative_status=(
                AdministrativeStatus(
                    status_code, ESTABLISHMENT_STATUS_LABELS.get(status_code)
                )
                if status_code is not None else None
            ),
            city=_optional_text(record, "libelle_commune"),
            is_headquarters=is_headquarters,
        ))
    return entries


def _establishment(data: dict[str, Any]) -> Establishment:
    """Lit l'identité et l'adresse d'un établissement présent dans la source."""
    return Establishment(
        siret=_optional_text(data, "siret"),
        address=_optional_text(data, "adresse"),
        city=_optional_text(data, "libelle_commune"),
        postal_code=_optional_text(data, "code_postal"),
    )


def _searched_establishment(
    company: dict[str, Any], query: str, headquarters: Establishment | None
) -> Establishment | None:
    """Identifie le SIRET demandé uniquement par concordance avec la source."""
    if len(query) != 14 or not query.isascii() or not query.isdecimal():
        return None
    if headquarters is not None and headquarters.siret == query:
        return headquarters
    for match in _matching_establishments(company) or []:
        if _optional_text(match, "siret") == query:
            return _establishment(match)
    return None


def _employee_band(company: dict[str, Any]) -> EmployeeBand | None:
    """Lit la tranche d'effectif salarié et son année de référence."""
    code = _optional_text(company, "tranche_effectif_salarie")
    if code is None:
        return None
    raw_year = _optional_text(company, "annee_tranche_effectif_salarie")
    if raw_year is not None and (len(raw_year) != 4 or not raw_year.isascii() or not raw_year.isdecimal()):
        raise CompanyDataError("L'année de la tranche d'effectif est invalide.")
    return EmployeeBand(
        code=code, label=EMPLOYEE_BAND_LABELS.get(code),
        year=int(raw_year) if raw_year is not None else None,
    )


def _representative_category(role: str | None) -> RepresentativeCategory:
    """Classe un rôle explicite, ou le laisse inconnu."""
    if role is None:
        return "other"
    normalized = " ".join(role.casefold().split())
    if "commissaire aux comptes" in normalized:
        return "auditor"
    if any(normalized == leader or normalized.startswith(f"{leader} ") for leader in LEADER_ROLES):
        return "leader"
    return "other"


def _representatives(company: dict[str, Any]) -> list[Representative]:
    """Conserve tous les acteurs retournés dans `dirigeants` par l'API."""
    raw_actors = company.get("dirigeants")
    if raw_actors is None:
        return []
    if not isinstance(raw_actors, list):
        raise CompanyDataError("La liste des dirigeants de l'API est invalide.")
    representatives: list[Representative] = []
    for actor in raw_actors:
        if not isinstance(actor, dict):
            raise CompanyDataError("Une entrée de la liste des dirigeants est invalide.")
        denomination = _optional_text(actor, "denomination")
        given_names = _optional_text(actor, "prenoms")
        surname = _optional_text(actor, "nom")
        personal_name = " ".join(part for part in (given_names, surname) if part)
        role = _optional_text(actor, "qualite")
        representatives.append(Representative(
            name=denomination or personal_name or None,
            role=role,
            entity_type=_optional_text(actor, "type_dirigeant"),
            category=_representative_category(role),
        ))
    return representatives


def _revenue_history(company: dict[str, Any]) -> list[RevenueExercise]:
    """Lit les CA numériques, du plus récent au plus ancien."""
    finances = company.get("finances")
    if finances is None:
        return []
    if not isinstance(finances, dict):
        raise CompanyDataError("Les données financières de l'API sont invalides.")
    history: list[RevenueExercise] = []
    for year, values in finances.items():
        if not isinstance(year, str) or len(year) != 4 or not year.isascii() or not year.isdecimal():
            raise CompanyDataError("Une année financière de l'API est invalide.")
        if not isinstance(values, dict):
            raise CompanyDataError(f"Les données financières de {year} sont invalides.")
        revenue = values.get("ca")
        if revenue is None:
            continue
        if (
            isinstance(revenue, bool)
            or not isinstance(revenue, (int, float))
            or (isinstance(revenue, float) and not math.isfinite(revenue))
            or revenue < 0
        ):
            raise CompanyDataError(f"Le chiffre d'affaires de {year} est invalide.")
        history.append(RevenueExercise(year=int(year), revenue_eur=revenue))
    return sorted(history, key=lambda exercise: exercise.year, reverse=True)


def _revenue_growth(history: list[RevenueExercise]) -> RevenueGrowth | None:
    """Compare les deux derniers CA de deux années consécutives."""
    if len(history) < 2:
        return None
    latest, previous = history[:2]
    if latest.year != previous.year + 1 or previous.revenue_eur <= 0:
        return None
    percent = (latest.revenue_eur - previous.revenue_eur) / previous.revenue_eur * 100
    return RevenueGrowth(from_year=previous.year, to_year=latest.year, percent=round(percent, 2))
