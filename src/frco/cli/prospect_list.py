"""Commande de création de listes de prospection."""

from pathlib import Path

import typer

from frco.clients.api_gouv_client import ApiGouvClient, ApiGouvError
from frco.formatters.csv_formatter import write_companies_csv
from frco.formatters.json_formatter import format_companies_json
from frco.services.company_service import CompanyDataError
from frco.services.prospect_list_service import (
    ProspectFilters, ProspectListError, ProspectListService,
)


def prospect_list(
    naf: str = typer.Argument(..., help="Sous-classe NAF (62.02A) ou classe (62.02)."),
    output: Path = typer.Option(..., "--output", "-o", help="Fichier CSV de destination."),
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
) -> None:
    """Exporte une liste d'entreprises en CSV et en JSON sur stdout.

    Args:
        naf: Code ou classe NAF rév. 2 de l'unité légale.
        output: Chemin du CSV à écrire.
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
    """
    filters = ProspectFilters(
        naf=naf, region=region, department=department, city=city,
        employees_min=employees_min, employees_max=employees_max,
        revenue_min=revenue_min, revenue_max=revenue_max,
        multi_site_only=multi_site_only,
        establishments_min=establishments_min, establishments_max=establishments_max,
        active_only=active_only,
    )
    try:
        companies = ProspectListService(ApiGouvClient()).build(filters)
        write_companies_csv(companies, output)
    except (ProspectListError, ApiGouvError, CompanyDataError, OSError) as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_companies_json(companies))
