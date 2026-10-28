"""Commande de recherche d'une entreprise."""

import typer

from frco.clients.api_gouv_client import ApiGouvClient, ApiGouvError
from frco.formatters.json_formatter import format_company_json
from frco.services.company_service import CompanyDataError, CompanyNotFoundError, CompanyService


def company(
    query: str = typer.Argument(..., help="Nom, SIREN ou SIRET à rechercher."),
    include_establishments: bool = typer.Option(
        False,
        "--include-establishments",
        help="Inclut les établissements disponibles et indique si la liste est complète.",
    ),
) -> None:
    """Affiche le premier résultat de l'API en JSON.

    Args:
        query: Valeur à transmettre telle quelle à l'API.
        include_establishments: Inclut le détail des établissements disponibles.
    """
    try:
        result = CompanyService(ApiGouvClient()).find_first(
            query, include_establishments=include_establishments
        )
    except (ApiGouvError, CompanyNotFoundError, CompanyDataError) as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(format_company_json(result))
