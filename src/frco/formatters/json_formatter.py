"""Sérialisation JSON sans mise en forme des données numériques."""

import json
import os
from dataclasses import asdict
from pathlib import Path
import tempfile

from frco.models.company import Company


def format_company_json(company: Company) -> str:
    """Sérialise une fiche en JSON lisible.

    Args:
        company: Fiche métier à sérialiser.

    Returns:
        JSON UTF-8 indenté, sans altérer les types des champs.
    """
    return json.dumps(asdict(company), ensure_ascii=False, indent=2)


def format_companies_json(companies: list[Company]) -> str:
    """Sérialise une liste de fiches avec le même schéma que ``company``.

    Args:
        companies: Entreprises sélectionnées.

    Returns:
        Tableau JSON lisible.
    """
    return json.dumps([asdict(company) for company in companies], ensure_ascii=False, indent=2)


def write_companies_json(companies: list[Company], output: Path) -> None:
    """Écrit le tableau JSON en UTF-8 avec remplacement atomique du fichier."""
    payload = format_companies_json(companies)
    target = output.resolve()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload + "\n")
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
