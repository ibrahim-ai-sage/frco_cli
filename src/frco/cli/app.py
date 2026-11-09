"""Point d'entrée du CLI frco."""

import typer

from frco.cli.company import company
from frco.cli.prospect_list import prospect_list


app = typer.Typer(help="Recherche d'entreprises françaises.", no_args_is_help=True, add_completion=False)


@app.callback()
def callback() -> None:
    """Expose les commandes du CLI."""


app.command(name="company", help="Affiche le premier résultat de l'API en JSON.")(company)
app.command(name="list", help="Construit une liste de comptes et exporte un JSON ou CSV.")(prospect_list)


def main() -> None:
    """Exécute l'application CLI."""
    app()
