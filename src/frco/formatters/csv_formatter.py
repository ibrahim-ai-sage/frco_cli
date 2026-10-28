"""Export CSV du schéma complet d'une fiche entreprise."""

import csv
from dataclasses import asdict, fields
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from frco.models.company import Company


CSV_COLUMNS = tuple(field.name for field in fields(Company))


def write_companies_csv(companies: list[Company], output: Path) -> None:
    """Écrit une ligne par SIREN avec chaque champ JSON en colonne.

    Args:
        companies: Fiches métier à exporter.
        output: Chemin du CSV demandé par l'utilisateur.

    Raises:
        OSError: Écriture impossible.
    """
    _write_records_csv([asdict(company) for company in companies], output)


def _write_records_csv(records: list[dict[str, Any]], output: Path) -> None:
    """Écrit des fiches déjà sérialisées, utile aussi pour réexporter un JSON."""
    columns = _csv_columns(records)
    target = output.resolve()
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="",
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for record in records:
                writer.writerow(_csv_row(record))
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _csv_columns(records: list[dict[str, Any]]) -> tuple[str, ...]:
    """Regroupe les colonnes racines et leurs chemins imbriqués dans l'ordre."""
    groups = {root: [root] for root in CSV_COLUMNS}
    seen = set(CSV_COLUMNS)
    for record in records:
        for root in CSV_COLUMNS:
            for path in _flatten(root, record[root]):
                if path not in seen:
                    groups[root].append(path)
                    seen.add(path)
    return tuple(path for paths in groups.values() for path in paths)


def _csv_row(record: dict[str, Any]) -> dict[str, str]:
    """Conserve la cellule JSON du parent et expose chaque enfant séparément."""
    return {
        path: _cell(value)
        for root in CSV_COLUMNS
        for path, value in _flatten(root, record[root]).items()
    }


def _flatten(path: str, value: Any) -> dict[str, Any]:
    """Déplie récursivement objets et tableaux en chemins de colonnes."""
    result = {path: value}
    if isinstance(value, dict):
        for key, child in value.items():
            result.update(_flatten(f"{path}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(_flatten(f"{path}[{index}]", child))
    return result


def _cell(value: Any) -> str:
    """Écrit les chaînes telles quelles et les autres valeurs en JSON valide."""
    return value if isinstance(value, str) else json.dumps(
        value, ensure_ascii=False, separators=(",", ":")
    )
