"""Sérialisation JSON sans mise en forme des données numériques."""

import json
from dataclasses import asdict

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
