"""Commande de création de listes de prospection."""

from pathlib import Path

import typer

from frco.clients.api_gouv_client import ApiGouvClient, ApiGouvError
from frco.formatters.csv_formatter import write_companies_csv
from frco.formatters.json_formatter import format_companies_json, write_companies_json
from frco.services.company_service import CompanyDataError
from frco.services.prospect_list_service import (
    ProspectFilters, ProspectListError, ProspectListService,
)
from frco.services.segmented_research import collect_segments, load_segments


def prospect_list(
    naf: str = typer.Argument(..., help="Sous-classe NAF (62.02A) ou classe (62.02)."),
    output: Path = typer.Option(
        Path("prospects.json"), "--output", "-o",
        help="Fichier JSON ou CSV de destination (format choisi par l'extension).",
    ),
    region: str | None = typer.Option(None, help="Code de région INSEE."),
    department: str | None = typer.Option(None, help="Code de département INSEE."),
    city: str | None = typer.Option(None, help="Nom de ville ou code de commune INSEE."),
    employees_min: int | None = typer.Option(None, help="Effectif salarié minimal."),
    employees_max: int | None = typer.Option(None, help="Effectif salarié maximal."),
    revenue_min: int | None = typer.Option(None, help="CA minimal en euros."),
    revenue_max: int | None = typer.Option(None, help="CA maximal en euros."),
    multi_site_only: bool = typer.Option(False, help="Entreprises multi-sites uniquement."),
    establishments_min: int | None = typer.Option(None, help="Nombre total minimal d'établissements."),
    establishments_max: int | None = typer.Option(None, help="Nombre total maximal d'établissements."),
    active_only: bool = typer.Option(False, help="Unités légales actives uniquement."),
    segments: Path | None = typer.Option(
        None, "--segments", help="Plan JSON de sous-recherches à collecter et fusionner par SIREN.",
    ),
) -> None:
    """Exporte une liste en JSON ou CSV et conserve le JSON sur stdout.

    Args:
        naf: Code ou classe NAF rév. 2 de l'unité légale.
        output: Fichier JSON ou CSV ; prospects.json par défaut.
        region: Code INSEE de région.
        department: Code INSEE de département.
        city: Nom de ville ou code INSEE de commune.
        employees_min: Borne basse d'effectif.
        employees_max: Borne haute d'effectif.
        revenue_min: Borne basse du CA en euros.
        revenue_max: Borne haute du CA en euros.
        multi_site_only: Exige plus d'un établissement actif.
        establishments_min: Borne basse du nombre total d'établissements.
        establishments_max: Borne haute du nombre total d'établissements.
        active_only: Exige une unité légale active.
        segments: Plan explicite de sous-recherches géographiques ou NAF.
    """
    extension = output.suffix.lower()
    if extension not in {".json", ".csv"}:
        typer.echo("Erreur : --output attend un fichier .json ou .csv.", err=True)
        raise typer.Exit(code=1)
    filters = ProspectFilters(
        naf=naf, region=region, department=department, city=city,
        employees_min=employees_min, employees_max=employees_max,
        revenue_min=revenue_min, revenue_max=revenue_max,
        multi_site_only=multi_site_only,
        establishments_min=establishments_min, establishments_max=establishments_max,
        active_only=active_only,
    )
    try:
        plan = None
        if segments is not None:
            if segments.resolve() == output.resolve():
                raise ProspectListError("Le plan de segments et le fichier de sortie doivent être distincts.")
            plan = load_segments(segments, filters)
        service = ProspectListService(ApiGouvClient())
        result = collect_segments(service, plan) if plan is not None else None
        companies = result.companies if result is not None else service.build(filters)
        if extension == ".csv":
            write_companies_csv(companies, output)
        else:
            write_companies_json(companies, output)
    except (ProspectListError, ApiGouvError, CompanyDataError, OSError) as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if result is not None:
        typer.echo(
            f"Segments terminés : {result.segment_count} ; occurrences : {result.occurrence_count} ; "
            f"SIREN uniques : {len(companies)}. Couverture limitée aux segments fournis.",
            err=True,
        )
    typer.echo(format_companies_json(companies))
