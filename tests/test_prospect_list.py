"""Tests ciblés de l'expansion NAF, de la pagination et de l'export GTM."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from frco.cli.app import app
from frco.formatters.csv_formatter import CSV_COLUMNS, write_companies_csv
from frco.services.activity_reference import resolve_naf_codes
from frco.services.company_service import CompanyService
from frco.services.prospect_list_service import (
    ProspectFilters, ProspectListError, ProspectListService,
)


def company_record(index: int, **changes: object) -> dict:
    """Crée une unité légale minimale avec un siège vérifiable."""
    siren = f"{100000000 + index:09d}"
    record = {
        "siren": siren,
        "nom_complet": f"SOCIETE {index}",
        "activite_principale": "62.02A",
        "etat_administratif": "A",
        "tranche_effectif_salarie": "12",
        "nombre_etablissements": 3,
        "nombre_etablissements_ouverts": 2,
        "finances": {"2024": {"ca": 250000}},
        "siege": {
            "siret": siren + "00011", "est_siege": True,
            "libelle_commune": "PARIS", "code_postal": "75001",
        },
    }
    record.update(changes)
    return record


class FakeClient:
    """Renvoie des pages de taille 25 en conservant les filtres demandés."""

    def __init__(self, records: list[dict], *, reported_total: int | None = None) -> None:
        self.records = records
        self.reported_total = len(records) if reported_total is None else reported_total
        self.calls: list[tuple[dict, int, int]] = []

    def search_companies(self, filters: dict, *, page: int, per_page: int = 25) -> dict:
        """Simule les métadonnées de pagination de l'API."""
        self.calls.append((dict(filters), page, per_page))
        total = self.reported_total
        return {
            "results": self.records[(page - 1) * per_page:page * per_page],
            "total_results": total,
            "total_pages": (total + per_page - 1) // per_page,
            "page": page,
        }


class ProspectListTests(unittest.TestCase):
    """Vérifie les critères V1 et le contrat des sorties."""

    def test_naf_class_expands_only_official_subclasses(self) -> None:
        """Une classe inclut tous ses codes officiels, sans code inventé."""
        self.assertEqual(resolve_naf_codes("62.02"), ("62.02A", "62.02B"))
        self.assertEqual(resolve_naf_codes("69.20"), ("69.20Z",))
        with self.assertRaises(ValueError):
            resolve_naf_codes("69.20A")

    def test_paginates_all_results_and_reuses_company_schema(self) -> None:
        """Vingt-six résultats exigent deux pages et gardent le schéma company."""
        client = FakeClient([company_record(index) for index in range(26)])
        companies = ProspectListService(client).build(ProspectFilters(naf="62.02"))
        self.assertEqual(len(companies), 26)
        self.assertEqual([call[1] for call in client.calls], [1, 2])
        self.assertEqual(client.calls[0][0]["activite_principale"], "62.02A,62.02B")
        self.assertEqual(companies[0].headquarters.siret, "10000000000011")
        self.assertIsNone(companies[0].searched_establishment)
        self.assertIsNone(companies[0].company_structure.establishments)

    def test_filters_unknowns_and_band_boundaries_conservatively(self) -> None:
        """Les inconnues et tranches chevauchant un seuil ne passent pas."""
        records = [
            company_record(1, tranche_effectif_salarie="12"),
            company_record(2, tranche_effectif_salarie="NN"),
            company_record(3, nombre_etablissements_ouverts=None),
            company_record(4, finances=None),
            company_record(5, tranche_effectif_salarie="11"),
        ]
        client = FakeClient(records)
        filters = ProspectFilters(
            naf="62.02A", employees_min=20, employees_max=49,
            revenue_min=200000, multi_site_only=True,
            establishments_min=2, active_only=True,
        )
        companies = ProspectListService(client).build(filters)
        self.assertEqual([company.siren for company in companies], ["100000001"])
        params = client.calls[0][0]
        self.assertEqual(params["tranche_effectif_salarie"], "12")
        self.assertEqual(params["ca_min"], 200000)
        self.assertEqual(params["etat_administratif"], "A")

    def test_city_name_checks_source_location(self) -> None:
        """La recherche textuelle ne suffit pas sans commune correspondante."""
        records = [company_record(1), company_record(2, siege={
            "siret": "10000000200011", "est_siege": True,
            "libelle_commune": "LYON", "code_postal": "69001",
        })]
        client = FakeClient(records)
        companies = ProspectListService(client).build(ProspectFilters(naf="62.02A", city="Paris"))
        self.assertEqual([company.siren for company in companies], ["100000001"])
        self.assertEqual(client.calls[0][0]["q"], "Paris")

    def test_api_cap_and_inconsistent_pages_fail(self) -> None:
        """Un export partiel n'est jamais présenté comme complet."""
        capped = FakeClient([], reported_total=10000)
        with self.assertRaisesRegex(ProspectListError, "10 000"):
            ProspectListService(capped).build(ProspectFilters(naf="62.02A"))
        inconsistent = FakeClient([company_record(1)], reported_total=2)
        with self.assertRaises(ProspectListError):
            ProspectListService(inconsistent).build(ProspectFilters(naf="62.02A"))

    def test_csv_columns_and_json_stdout(self) -> None:
        """Les champs imbriqués ont leur colonne et le parent reste fidèle."""
        client = FakeClient([company_record(
            1,
            finances={"2024": {"ca": 250000}, "2023": {"ca": 200000}},
            dirigeants=[{
                "prenoms": "Camille", "nom": "Exemple", "qualite": "Président de SAS",
                "type_dirigeant": "personne physique",
            }],
        )])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prospects.csv"
            with patch("frco.cli.prospect_list.ApiGouvClient", return_value=client):
                result = CliRunner().invoke(app, ["list", "62.02A", "--output", str(path)])
            self.assertEqual(result.exit_code, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            output = json.loads(result.stdout)
            self.assertEqual(len(output), 1)
            self.assertEqual(output[0]["headquarters"]["siret"], "10000000100011")
            self.assertEqual(output[0]["revenue_history"][0]["revenue_eur"], 250000)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertTrue(set(CSV_COLUMNS).issubset(reader.fieldnames))
                row = next(reader)
                self.assertEqual(row["siren"], "100000001")
                self.assertIsNone(json.loads(row["searched_establishment"]))
                self.assertEqual(json.loads(row["headquarters"])["siret"], "10000000100011")
                self.assertEqual(row["headquarters.siret"], "10000000100011")
                self.assertEqual(json.loads(row["company_structure"])["is_multi_site"], True)
                self.assertEqual(row["company_structure.total_establishments"], "3")
                self.assertEqual(row["company_structure.active_establishments"], "2")
                self.assertEqual(row["company_structure.is_multi_site"], "true")
                self.assertEqual(row["company_structure.establishments"], "null")
                self.assertEqual(row["company_structure.establishments_complete"], "null")
                self.assertEqual(json.loads(row["representatives"])[0]["category"], "leader")
                self.assertEqual(row["representatives[0].name"], "Camille Exemple")
                self.assertEqual(json.loads(row["revenue_history"])[0]["revenue_eur"], 250000)
                self.assertEqual(row["revenue_history[0].year"], "2024")
                self.assertEqual(row["revenue_history[0].revenue_eur"], "250000")
                self.assertEqual(json.loads(row["revenue_growth"])["percent"], 25.0)
                self.assertEqual(row["revenue_growth.percent"], "25.0")
                self.assertEqual(json.loads(row["metadata"]), output[0]["metadata"])
                self.assertEqual(row["metadata.source"], "API Recherche d'entreprises")
                for key, value in output[0].items():
                    with self.subTest(key=key):
                        self.assertEqual(
                            row[key] if isinstance(value, str) else json.loads(row[key]),
                            value,
                        )
                self.assertIsNone(next(reader, None))

    def test_failed_search_does_not_write_csv(self) -> None:
        """Le fichier demandé reste absent si l'API plafonne les résultats."""
        client = FakeClient([], reported_total=10000)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prospects.csv"
            with patch("frco.cli.prospect_list.ApiGouvClient", return_value=client):
                result = CliRunner().invoke(app, ["list", "62.02A", "-o", str(path)])
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("10 000", result.stderr)
            self.assertFalse(path.exists())

    def test_csv_preserves_missing_objects_and_empty_arrays(self) -> None:
        """Les valeurs inconnues restent null et les tableaux absents restent []."""
        raw = company_record(
            2, siege=None, etat_administratif=None,
            tranche_effectif_salarie=None, dirigeants=None, finances=None,
            nombre_etablissements=None, nombre_etablissements_ouverts=None,
        )
        company = CompanyService(FakeClient([])).from_result(raw)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.csv"
            write_companies_csv([company], path)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream))
        self.assertIsNone(json.loads(row["headquarters"]))
        self.assertIsNone(json.loads(row["administrative_status"]))
        self.assertIsNone(json.loads(row["company_structure"])["is_multi_site"])
        self.assertEqual(row["company_structure.is_multi_site"], "null")
        self.assertEqual(json.loads(row["representatives"]), [])
        self.assertEqual(json.loads(row["revenue_history"]), [])
        self.assertIsNone(json.loads(row["revenue_growth"]))

    def test_csv_expands_variable_length_representative_lists(self) -> None:
        """Un acteur supplémentaire reçoit des colonnes sans changer les lignes."""
        first = company_record(1, dirigeants=[{
            "prenoms": "A", "nom": "Un", "qualite": "Président",
            "type_dirigeant": "personne physique",
        }])
        second = company_record(2, dirigeants=[
            {"prenoms": "B", "nom": "Deux", "qualite": "Président",
             "type_dirigeant": "personne physique"},
            {"denomination": "AUDIT SA", "qualite": "Commissaire aux comptes titulaire",
             "type_dirigeant": "personne morale"},
        ])
        service = CompanyService(FakeClient([]))
        companies = [service.from_result(first), service.from_result(second)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "representatives.csv"
            write_companies_csv(companies, path)
            with path.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["representatives[1].name"], "")
        self.assertEqual(rows[1]["representatives[1].name"], "AUDIT SA")
        self.assertEqual(rows[1]["representatives[1].category"], "auditor")


if __name__ == "__main__":
    unittest.main()
