"""Libellés NAF rév. 2 issus des listes officielles de l'Insee."""

import csv
from importlib.resources import files
import re


def naf_label(code: str | None) -> str | None:
    """Retourne le libellé d'une sous-classe NAF rév. 2.

    Args:
        code: Code NAF transmis par l'API.

    Returns:
        Libellé officiel, ou ``None`` si le code est absent de la référence.
    """
    return _label("naf_rev2_subclasses.csv", code)


def section_label(code: str | None) -> str | None:
    """Retourne le libellé d'une section NAF rév. 2.

    Args:
        code: Lettre de section transmise par l'API.

    Returns:
        Libellé officiel, ou ``None`` si la section est inconnue.
    """
    return _label("naf_rev2_sections.csv", code)


def resolve_naf_codes(value: str) -> tuple[str, ...]:
    """Résout une sous-classe ou toutes les sous-classes d'une classe NAF rév. 2.

    Args:
        value: Code complet (ex. ``62.02A``) ou classe (ex. ``62.02``).

    Returns:
        Codes officiels triés de la référence embarquée.

    Raises:
        ValueError: Format ou code absent de la nomenclature.
    """
    normalized = value.strip().upper()
    if not re.fullmatch(r"\d{2}\.\d{2}[A-Z]?", normalized):
        raise ValueError("Le code NAF doit être une classe 00.00 ou une sous-classe 00.00A.")

    reference = files("frco").joinpath("data", "naf_rev2_subclasses.csv")
    with reference.open("r", encoding="utf-8", newline="") as source:
        codes = {
            row["code"]
            for row in csv.DictReader(source)
            if row["code"] == normalized or (
                len(normalized) == 5 and row["code"].startswith(normalized)
            )
        }
    if not codes:
        raise ValueError(f"Code ou classe NAF rév. 2 inconnu : {value!r}.")
    return tuple(sorted(codes))


def _label(filename: str, code: str | None) -> str | None:
    """Cherche un code dans une référence CSV embarquée."""
    if code is None:
        return None
    reference = files("frco").joinpath("data", filename)
    with reference.open("r", encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["code"] == code:
                return row["label"]
    return None
