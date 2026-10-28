"""Vérifications ciblées du schéma et de la normalisation."""

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import unittest

from frco.formatters.json_formatter import format_company_json
from frco.services.company_service import CompanyService


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "api_response_microsoft_france.json"


class FakeClient:
    """Renvoie une réponse contrôlée en enregistrant la requête reçue."""

    def __init__(self, payload: dict) -> None:
        """Mémorise la réponse simulée."""
        self.payload = payload
        self.query: str | None = None
        self.calls: list[tuple[str, int | None]] = []
        self.responses: dict[str, dict] = {}

    def search(self, query: str, *, establishment_limit: int | None = None) -> dict:
        """Renvoie la réponse sans modifier l'argument."""
        self.query = query
        self.calls.append((query, establishment_limit))
        return self.responses.get(query, self.payload)


class CompanyServiceTests(unittest.TestCase):
    """Couvre le contrat JSON pour les cas SIREN, SIRET et incomplets."""

    def setUp(self) -> None:
        """Recharge une copie de la réponse API enregistrée."""
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.client = FakeClient(self.payload)
        self.service = CompanyService(self.client)

    def test_siren_uses_verified_headquarters_and_numeric_revenue(self) -> None:
        """Une recherche SIREN conserve les données du siège et les types."""
        company = self.service.find_first("327733184")
        output = json.loads(format_company_json(company))
        self.assertEqual(self.client.query, "327733184")
        self.assertEqual(output["siren"], "327733184")
        self.assertNotIn("headquarters_siret", output)
        self.assertEqual(output["headquarters"]["siret"], "32773318400516")
        self.assertEqual(output["headquarters"]["city"], "ISSY-LES-MOULINEAUX")
        self.assertIsNone(output["searched_establishment"])
        self.assertEqual(output["company_structure"]["total_establishments"], 56)
        self.assertEqual(output["company_structure"]["active_establishments"], 9)
        self.assertIs(output["company_structure"]["is_multi_site"], True)
        self.assertNotIn("headquarters_siret", output["company_structure"])
        self.assertIsNone(output["company_structure"]["establishments"])
        self.assertIsNone(output["company_structure"]["establishments_complete"])
        self.assertEqual(output["administrative_status"], {"code": "A", "label": "Active"})
        self.assertEqual(output["revenue_history"], [{"year": 2024, "revenue_eur": 5364428050}])
        self.assertIsNone(output["revenue_growth"])
        self.assertEqual(output["employee_band"]["code"], "42")
        self.assertEqual(output["employee_band"]["label"], "1 000 à 1 999 salariés")
        self.assertEqual(output["metadata"]["source"], "API Recherche d'entreprises")
        self.assertEqual(datetime.fromisoformat(output["metadata"]["retrieved_at"]).utcoffset().total_seconds(), 0)
        self.assertNotIn("status", output)
        self.assertNotIn("leaders", output)
        self.assertNotIn("is_growing", output)

    def test_siret_branch_is_distinct_from_headquarters(self) -> None:
        """L'adresse du SIRET demandé provient de son entrée correspondante."""
        company = self.service.find_first("32773318400243")
        self.assertEqual(self.client.query, "32773318400243")
        self.assertEqual(company.headquarters.siret, "32773318400516")
        self.assertEqual(company.searched_establishment.siret, "32773318400243")
        self.assertEqual(company.searched_establishment.city, "VILLEBON-SUR-YVETTE")
        self.assertNotEqual(company.searched_establishment.address, company.headquarters.address)

    def test_siret_of_headquarters_is_explicitly_returned(self) -> None:
        """Le siège est aussi l'établissement recherché si les SIRET concordent."""
        company = self.service.find_first("32773318400516")
        self.assertEqual(company.searched_establishment, company.headquarters)

    def test_unmatched_siret_does_not_borrow_headquarters_address(self) -> None:
        """Une entrée absente de la réponse reste inconnue."""
        company = self.service.find_first("32773318499999")
        self.assertIsNone(company.searched_establishment)
        self.assertIsNotNone(company.headquarters)

    def test_explicitly_non_headquarters_source_is_not_labeled_headquarters(self) -> None:
        """Un indicateur source contradictoire empêche l'attribution au siège."""
        self.payload["results"][0]["siege"]["est_siege"] = False
        company = self.service.find_first("32773318400516")
        self.assertIsNone(company.headquarters)
        self.assertEqual(company.searched_establishment.siret, "32773318400516")

    def test_representatives_include_auditor_and_unknown_role(self) -> None:
        """La liste source est conservée avec une catégorie prudente."""
        self.payload["results"][0]["dirigeants"].append({
            "prenoms": "Camille", "nom": "Test", "qualite": "Mandataire spécial",
            "type_dirigeant": "personne physique",
        })
        company = self.service.find_first("327733184")
        self.assertEqual([item.category for item in company.representatives],
                         ["leader", "auditor", "other"])
        self.assertEqual(company.representatives[1].role, "Commissaire aux comptes titulaire")
        self.assertEqual(company.representatives[2].name, "Camille Test")
        self.assertEqual(company.representatives[2].entity_type, "personne physique")

    def test_missing_data_remains_unknown(self) -> None:
        """Aucune valeur manquante ne devient zéro ou faux."""
        first = self.payload["results"][0]
        first["siege"] = None
        first["matching_etablissements"] = None
        first["etat_administratif"] = None
        first["tranche_effectif_salarie"] = None
        first["dirigeants"] = None
        first["finances"] = None
        first["nombre_etablissements"] = None
        first["nombre_etablissements_ouverts"] = None
        company = self.service.find_first("32773318400243")
        self.assertIsNone(company.headquarters)
        self.assertIsNone(company.searched_establishment)
        self.assertIsNone(company.administrative_status)
        self.assertIsNone(company.employee_band)
        self.assertEqual(company.representatives, [])
        self.assertEqual(company.revenue_history, [])
        self.assertIsNone(company.revenue_growth)
        self.assertIsNone(company.company_structure.total_establishments)
        self.assertIsNone(company.company_structure.active_establishments)
        self.assertIsNone(company.company_structure.is_multi_site)

    def test_detailed_list_uses_verified_name_enrichment_for_siren(self) -> None:
        """Une recherche SIREN complète sa liste seulement avec le même SIREN."""
        first = self.payload["results"][0]
        first["nombre_etablissements"] = 2
        first["nombre_etablissements_ouverts"] = 1
        first["matching_etablissements"] = []
        other = deepcopy(first["siege"])
        other.update({
            "siret": "32773318400243", "libelle_commune": "VILLEBON-SUR-YVETTE",
            "etat_administratif": "F", "est_siege": False,
        })
        candidate = {
            "siren": "327733184",
            "matching_etablissements": [first["siege"], other],
        }
        self.client.responses["MICROSOFT FRANCE"] = {"results": [candidate]}

        structure = self.service.find_first(
            "327733184", include_establishments=True
        ).company_structure

        self.assertEqual(self.client.calls, [
            ("327733184", 100), ("MICROSOFT FRANCE", 100)
        ])
        self.assertEqual(len(structure.establishments), 2)
        self.assertIsNone(structure.establishments_complete)
        self.assertIs(structure.establishments[0].is_headquarters, True)
        self.assertEqual(structure.establishments[0].administrative_status.label, "Actif")
        self.assertIs(structure.establishments[1].is_headquarters, False)
        self.assertEqual(structure.establishments[1].administrative_status.label, "Fermé")
        self.assertIs(structure.is_multi_site, False)

    def test_detailed_list_rejects_other_legal_entity(self) -> None:
        """Une réponse complémentaire d'un autre SIREN n'est pas mélangée."""
        first = self.payload["results"][0]
        first["matching_etablissements"] = []
        self.client.responses["MICROSOFT FRANCE"] = {"results": [{
            "siren": "999999999",
            "matching_etablissements": [first["siege"]],
        }]}
        structure = self.service.find_first(
            "327733184", include_establishments=True
        ).company_structure
        self.assertEqual(structure.establishments, [])
        self.assertIs(structure.establishments_complete, False)

    def test_detailed_list_rejects_foreign_siret(self) -> None:
        """Même un résultat du bon SIREN ne mélange pas un SIRET étranger."""
        first = self.payload["results"][0]
        first["nombre_etablissements"] = 1
        first["matching_etablissements"] = [{
            "siret": "99999999900011",
            "etat_administratif": "A",
            "libelle_commune": "PARIS",
            "est_siege": False,
        }]
        structure = self.service.find_first(
            "MICROSOFT FRANCE", include_establishments=True
        ).company_structure
        self.assertEqual(structure.establishments, [])
        self.assertIs(structure.establishments_complete, False)

    def test_detailed_list_marks_partial_results(self) -> None:
        """Les établissements retournés ne sont pas confondus avec le total."""
        structure = self.service.find_first(
            "MICROSOFT FRANCE", include_establishments=True
        ).company_structure
        self.assertEqual(len(structure.establishments), 10)
        self.assertEqual(structure.total_establishments, 56)
        self.assertIs(structure.establishments_complete, False)
        self.assertEqual(self.client.calls, [("MICROSOFT FRANCE", 100)])

    def test_unknown_active_count_stays_unknown(self) -> None:
        """Le total connu ne remplace pas le nombre actif manquant."""
        self.payload["results"][0]["nombre_etablissements_ouverts"] = None
        structure = self.service.find_first("327733184").company_structure
        self.assertEqual(structure.total_establishments, 56)
        self.assertIsNone(structure.active_establishments)
        self.assertIsNone(structure.is_multi_site)

    def test_absent_list_and_empty_list_are_distinct(self) -> None:
        """Une liste omise est inconnue ; une liste vide est observée."""
        first = self.payload["results"][0]
        first["matching_etablissements"] = None
        absent = self.service.find_first(
            "MICROSOFT FRANCE", include_establishments=True
        ).company_structure
        self.assertIsNone(absent.establishments)
        self.assertIsNone(absent.establishments_complete)

        first["matching_etablissements"] = []
        empty = self.service.find_first(
            "MICROSOFT FRANCE", include_establishments=True
        ).company_structure
        self.assertEqual(empty.establishments, [])
        self.assertIs(empty.establishments_complete, False)

    def test_equal_count_on_one_page_does_not_prove_completeness(self) -> None:
        """L'égalité des compteurs n'est pas une garantie de pagination."""
        first = self.payload["results"][0]
        first["nombre_etablissements"] = 1
        first["matching_etablissements"] = [first["siege"]]
        structure = self.service.find_first(
            "MICROSOFT FRANCE", include_establishments=True
        ).company_structure
        self.assertEqual(len(structure.establishments), 1)
        self.assertIsNone(structure.establishments_complete)

    def test_representative_keeps_source_surname_with_parentheses(self) -> None:
        """Le nom renvoyé par l'API est conservé sans correction heuristique."""
        self.payload["results"][0]["dirigeants"] = [{
            "prenoms": "FRANCIS", "nom": "HOLDER (HOLDER)",
            "qualite": "Président", "type_dirigeant": "personne physique",
        }]
        company = self.service.find_first("327733184")
        self.assertEqual(company.representatives[0].name, "FRANCIS HOLDER (HOLDER)")

    def test_company_metrics_do_not_use_establishment_fields(self) -> None:
        """Effectif et CA proviennent de l'unité légale, même pour un SIRET."""
        first = self.payload["results"][0]
        first["tranche_effectif_salarie"] = "42"
        first["finances"] = {"2024": {"ca": 500}}
        first["siege"]["tranche_effectif_salarie"] = "01"
        first["siege"]["finances"] = {"2024": {"ca": 10}}
        first["matching_etablissements"][0]["tranche_effectif_salarie"] = "02"
        first["matching_etablissements"][0]["finances"] = {"2024": {"ca": 20}}

        company = self.service.find_first("32773318400243")
        self.assertEqual(company.employee_band.code, "42")
        self.assertEqual(company.revenue_history[0].revenue_eur, 500)

    def test_unknown_status_has_no_invented_label(self) -> None:
        """Un code non documenté est conservé sans libellé."""
        self.payload["results"][0]["etat_administratif"] = "X"
        company = self.service.find_first("327733184")
        self.assertEqual(company.administrative_status.code, "X")
        self.assertIsNone(company.administrative_status.label)

    def test_growth_requires_consecutive_years_and_positive_base(self) -> None:
        """Le calcul repose sur deux CA annuels consécutifs."""
        cases = [
            ({"2024": {"ca": 120}, "2023": {"ca": 100}}, (2023, 2024, 20.0)),
            ({"2024": {"ca": 80}, "2023": {"ca": 100}}, (2023, 2024, -20.0)),
            ({"2024": {"ca": 120}, "2022": {"ca": 100}}, None),
            ({"2024": {"ca": 120}, "2023": {"ca": 0}}, None),
            ({"2024": {"ca": 120}, "2023": {"ca": None}, "2022": {"ca": 100}}, None),
        ]
        for finances, expected in cases:
            with self.subTest(finances=finances):
                self.payload["results"][0]["finances"] = finances
                growth = self.service.find_first("327733184").revenue_growth
                actual = None if growth is None else (growth.from_year, growth.to_year, growth.percent)
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
