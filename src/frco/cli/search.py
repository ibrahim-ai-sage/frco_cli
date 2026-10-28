"""Commande de recherche directe dans l'API Recherche d'entreprises."""

import json

import typer

from frco.clients.api_gouv_client import ApiGouvClient, ApiGouvError


CATEGORY_VALUES = {"PME", "ETI", "GE"}


def _field_path(value: str) -> tuple[str, ...]:
    """Valide un chemin de champ relatif à une entreprise."""
    path = tuple(value.split("."))
    if any(not part or part != part.strip() for part in path):
        raise ValueError("un champ à exclure est vide ou mal formé.")
    return path


def _remove_field(value: object, path: tuple[str, ...]) -> None:
    """Retire un champ dans un objet, y compris dans chaque élément d'une liste."""
    if isinstance(value, list):
        for item in value:
            _remove_field(item, path)
    elif isinstance(value, dict):
        if len(path) == 1:
            value.pop(path[0], None)
        elif path[0] in value:
            _remove_field(value[path[0]], path[1:])


def _matches_exclusion(value: object, path: tuple[str, ...], expected: str) -> bool:
    """Cherche une valeur de champ, y compris dans les éléments d'une liste."""
    if isinstance(value, list):
        return any(_matches_exclusion(item, path, expected) for item in value)
    if not isinstance(value, dict) or path[0] not in value:
        return False
    field_value = value[path[0]]
    if len(path) > 1:
        return _matches_exclusion(field_value, path[1:], expected)
    if isinstance(field_value, (dict, list)):
        return False
    return str(field_value).casefold() == expected.casefold()


def search(
    query: str = typer.Argument(..., help="Nom, SIREN ou SIRET à rechercher."),
    page: int = typer.Option(1, "--page", min=1, help="Page de résultats (à partir de 1)."),
    per_page: int = typer.Option(
        10, "--per-page", min=1, max=25, help="Nombre de résultats par page (1 à 25)."
    ),
    exclude: list[str] | None = typer.Option(
        None, "--exclude", help="Exclut les entreprises : ETI ou champ=valeur (répétable)."
    ),
    exclude_field: list[str] | None = typer.Option(
        None, "--exclude-field", help="Champ à retirer du JSON, ex. siege.adresse."
    ),
) -> None:
    """Affiche une page de résultats de l'API en JSON."""
    if not query.strip():
        typer.echo("Erreur : la recherche ne peut pas être vide.", err=True)
        raise typer.Exit(code=1)

    field_names = list(exclude_field or [])
    conditions: list[tuple[tuple[str, ...], str]] = []
    try:
        for item in exclude or []:
            if "=" in item:
                field, value = item.split("=", 1)
                if not value.strip():
                    raise ValueError("une valeur à exclure est vide.")
                conditions.append((_field_path(field), value.strip()))
            elif item.upper() in CATEGORY_VALUES:
                conditions.append((("categorie_entreprise",), item.upper()))
            else:
                raise ValueError("--exclude attend ETI, PME, GE ou champ=valeur.")
        paths = [_field_path(field) for field in field_names]
    except ValueError as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1)

    try:
        payload = ApiGouvClient().search_companies({"q": query}, page=page, per_page=per_page)
    except ApiGouvError as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(code=1) from exc
    results = payload.get("results")
    if not isinstance(results, list):
        typer.echo("Erreur : la réponse de l'API ne contient pas de liste de résultats.", err=True)
        raise typer.Exit(code=1)
    if conditions:
        payload["results"] = [
            company for company in results
            if not any(_matches_exclusion(company, path, value) for path, value in conditions)
        ]
        payload["excluded_results_on_page"] = len(results) - len(payload["results"])
    for company in payload["results"]:
        for path in paths:
            _remove_field(company, path)
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
