"""Exécution d'un découpage explicite sans modifier le périmètre métier."""

from dataclasses import dataclass, replace
import json
from pathlib import Path

from frco.clients.api_gouv_client import ApiGouvError
from frco.models.company import Company
from frco.services.activity_reference import resolve_naf_codes
from frco.services.company_service import CompanyDataError
from frco.services.prospect_list_service import (
    COMMUNE_CODE, ProspectFilters, ProspectListError, ProspectListService,
)


@dataclass(frozen=True)
class ResearchSegment:
    """Segment nommé avec tous les critères hérités de la recherche initiale."""

    identifier: str
    filters: ProspectFilters


@dataclass(frozen=True)
class SegmentedResult:
    """Union des fiches collectées et compteurs d'exécution des segments."""

    companies: list[Company]
    segment_count: int
    occurrence_count: int


def load_segments(path: Path, base: ProspectFilters) -> list[ResearchSegment]:
    """Valide tout le plan avant le réseau ; seuls géographie et NAF varient.

    La validation préserve les contraintes initiales mais ne prouve pas que
    les segments couvrent toute la zone : cette preuve revient au planificateur.
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProspectListError(f"Plan de segments illisible : {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"version", "segments"}:
        raise ProspectListError("Le plan doit contenir uniquement version et segments.")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise ProspectListError("Version du plan non prise en charge : version doit valoir 1.")
    entries = payload["segments"]
    if not isinstance(entries, list) or not entries:
        raise ProspectListError("Le plan doit contenir une liste non vide de segments.")
    if base.city and not COMMUNE_CODE.fullmatch(base.city):
        raise ProspectListError("Un plan de segments exige un code INSEE pour --city, pas un nom.")
    try:
        base_codes = set(resolve_naf_codes(base.naf))
    except ValueError as exc:
        raise ProspectListError(str(exc)) from exc

    segments: list[ResearchSegment] = []
    identifiers: set[str] = set()
    effective_filters: set[ProspectFilters] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or "id" not in entry:
            raise ProspectListError(f"Segment {index} : objet avec id requis.")
        if set(entry) - {"id", "naf", "region", "department", "city"}:
            raise ProspectListError(f"Segment {index} : seuls id, naf, region, department et city sont acceptés.")
        if any(not isinstance(value, str) or not value.strip() or value != value.strip()
               for value in entry.values()):
            raise ProspectListError(f"Segment {index} : les valeurs doivent être des chaînes non vides sans espaces périphériques.")
        identifier = entry["id"]
        if identifier in identifiers:
            raise ProspectListError(f"Identifiant de segment répété : {identifier}.")
        overrides = {key: value for key, value in entry.items() if key != "id"}
        for key in ("region", "department", "city"):
            if key in overrides and getattr(base, key) is not None:
                if overrides[key].upper() != getattr(base, key).upper():
                    raise ProspectListError(f"Segment {identifier} : ne peut pas remplacer le critère initial {key}.")
        if "city" in overrides and not COMMUNE_CODE.fullmatch(overrides["city"]):
            raise ProspectListError(f"Segment {identifier} : city doit être un code INSEE de commune.")
        try:
            codes = set(resolve_naf_codes(overrides.get("naf", base.naf)))
        except ValueError as exc:
            raise ProspectListError(f"Segment {identifier} : {exc}") from exc
        if not codes.issubset(base_codes):
            raise ProspectListError(f"Segment {identifier} : NAF hors du périmètre initial.")
        filters = replace(base, **overrides)
        if filters in effective_filters:
            raise ProspectListError(f"Segment {identifier} : critères identiques à un autre segment.")
        identifiers.add(identifier)
        effective_filters.add(filters)
        segments.append(ResearchSegment(identifier, filters))
    return segments


def collect_segments(service: ProspectListService, segments: list[ResearchSegment]) -> SegmentedResult:
    """Collecte séquentiellement ; aucun résultat global si une feuille échoue."""
    unique: dict[str, Company] = {}
    occurrences = 0
    for segment in segments:
        try:
            companies = service.build(segment.filters)
        except (ProspectListError, ApiGouvError, CompanyDataError) as exc:
            raise ProspectListError(f"Segment {segment.identifier} : {exc}") from exc
        occurrences += len(companies)
        for company in companies:
            if not company.siren:
                raise ProspectListError(f"Segment {segment.identifier} : fiche sans SIREN.")
            previous = unique.get(company.siren)
            # La fiche entière la plus récente est conservée, sans inventer
            # une union exhaustive des établissements des différentes réponses.
            if previous is None or company.metadata.retrieved_at > previous.metadata.retrieved_at:
                unique[company.siren] = company
    return SegmentedResult(list(unique.values()), len(segments), occurrences)
