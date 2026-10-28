"""Schéma public d'une fiche entreprise."""

from dataclasses import dataclass
from typing import Literal


RepresentativeCategory = Literal["leader", "auditor", "other"]


@dataclass(frozen=True)
class AdministrativeStatus:
    """Code administratif et libellé documenté d'une entité."""

    code: str
    label: str | None


@dataclass(frozen=True)
class Establishment:
    """Identité et adresse d'un établissement attesté par la source."""

    siret: str | None
    address: str | None
    city: str | None
    postal_code: str | None


@dataclass(frozen=True)
class EstablishmentEntry:
    """Résumé d'un établissement fourni par l'API."""

    siret: str
    administrative_status: AdministrativeStatus | None
    city: str | None
    is_headquarters: bool | None


@dataclass(frozen=True)
class CompanyStructure:
    """Compte les établissements d'une unité légale et décrit son réseau."""

    total_establishments: int | None
    active_establishments: int | None
    is_multi_site: bool | None
    establishments: list[EstablishmentEntry] | None
    establishments_complete: bool | None


@dataclass(frozen=True)
class EmployeeBand:
    """Tranche d'effectif salariée publiée pour l'entreprise."""

    code: str
    label: str | None
    year: int | None


@dataclass(frozen=True)
class Representative:
    """Acteur de la liste « dirigeants » de l'API, avec rôle normalisé."""

    name: str | None
    role: str | None
    entity_type: str | None
    category: RepresentativeCategory


@dataclass(frozen=True)
class RevenueExercise:
    """Chiffre d'affaires numérique en euros pour un exercice."""

    year: int
    revenue_eur: int | float


@dataclass(frozen=True)
class RevenueGrowth:
    """Variation du CA entre deux exercices annuels consécutifs."""

    from_year: int
    to_year: int
    percent: float


@dataclass(frozen=True)
class Metadata:
    """Provenance et instant de récupération de la fiche."""

    source: str
    retrieved_at: str


@dataclass(frozen=True)
class Company:
    """Fiche d'une unité légale, de son siège et de l'établissement cherché."""

    name: str | None
    siren: str | None
    headquarters: Establishment | None
    searched_establishment: Establishment | None
    company_structure: CompanyStructure
    administrative_status: AdministrativeStatus | None
    naf_code: str | None
    naf_label: str | None
    activity_section: str | None
    activity_section_label: str | None
    employee_band: EmployeeBand | None
    representatives: list[Representative]
    revenue_history: list[RevenueExercise]
    revenue_growth: RevenueGrowth | None
    metadata: Metadata
