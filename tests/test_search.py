"""Contrat de la commande de recherche directe."""

import json
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from frco.cli.app import app
from frco.clients.api_gouv_client import ApiGouvError


class SearchCliTests(unittest.TestCase):
    def test_query_and_pagination_are_forwarded_without_changes(self) -> None:
        payload = {
            "results": [{"nom_complet": "SOCIÉTÉ EXEMPLE", "siren": "123456789"}],
            "page": 2,
            "total_pages": 3,
            "total_results": 50,
        }
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(
                app, ["search", "Société Exemple", "--page", "2", "--per-page", "25"]
            )

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "Société Exemple"}, page=2, per_page=25)
        self.assertEqual(json.loads(result.stdout), payload)
        self.assertEqual(result.stderr, "")

    def test_empty_results_are_valid(self) -> None:
        payload = {"results": [], "page": 1, "total_pages": 0, "total_results": 0}
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(app, ["search", "inexistant"])

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "inexistant"}, page=1, per_page=10)
        self.assertEqual(json.loads(result.stdout)["results"], [])

    def test_api_error_goes_to_stderr(self) -> None:
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            side_effect=ApiGouvError("API indisponible"),
        ):
            result = CliRunner().invoke(app, ["search", "exemple"])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("API indisponible", result.stderr)

    def test_excluded_fields_are_removed_only_after_api_response(self) -> None:
        payload = {
            "results": [{
                "siren": "123456789", "dirigeants": [{"nom": "Dupont"}],
                "finances": {"2024": {"ca": 100}}, "siege": {"adresse": "Paris"},
            }],
            "page": 1, "total_results": 1,
        }
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(
                app, ["search", "exemple", "--exclude-field", "dirigeants",
                      "--exclude-field", "finances"]
            )

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "exemple"}, page=1, per_page=10)
        output = json.loads(result.stdout)
        self.assertEqual(output["results"], [{"siren": "123456789", "siege": {"adresse": "Paris"}}])
        self.assertEqual(output["total_results"], 1)

    def test_nested_exclusions_apply_to_dicts_and_each_list_item(self) -> None:
        payload = {"results": [{
            "siege": {"adresse": "Paris", "siret": "12345678900001"},
            "dirigeants": [{"nom": "Dupont", "qualite": "Président"},
                           {"nom": "Martin", "qualite": "Directeur général"}],
        }], "page": 1}
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(app, [
                "search", "exemple", "--exclude-field", "siege.adresse",
                "--exclude-field", "dirigeants.nom",
            ])

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "exemple"}, page=1, per_page=10)
        company = json.loads(result.stdout)["results"][0]
        self.assertEqual(company["siege"], {"siret": "12345678900001"})
        self.assertEqual(company["dirigeants"], [
            {"qualite": "Président"}, {"qualite": "Directeur général"}
        ])

    def test_malformed_exclusion_is_rejected_before_api_call(self) -> None:
        with patch("frco.clients.api_gouv_client.ApiGouvClient.search_companies") as api_search:
            result = CliRunner().invoke(app, ["search", "exemple", "--exclude-field", "siege..adresse"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("mal formé", result.stderr)
        api_search.assert_not_called()

    def test_exclude_without_value_or_category_is_rejected(self) -> None:
        with patch("frco.clients.api_gouv_client.ApiGouvClient.search_companies") as api_search:
            result = CliRunner().invoke(app, ["search", "conseil", "--exclude", "dirigeants"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("champ=valeur", result.stderr)
        api_search.assert_not_called()

    def test_exclude_category_filters_companies_after_api_call(self) -> None:
        payload = {
            "results": [
                {"siren": "111111111", "categorie_entreprise": "ETI"},
                {"siren": "222222222", "categorie_entreprise": "PME"},
                {"siren": "333333333", "categorie_entreprise": "GE"},
            ],
            "page": 1, "total_results": 3, "total_pages": 1,
        }
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(app, ["search", "conseil", "--exclude", "ETI"])

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "conseil"}, page=1, per_page=10)
        output = json.loads(result.stdout)
        self.assertEqual([company["siren"] for company in output["results"]], [
            "222222222", "333333333"
        ])
        self.assertEqual(output["excluded_results_on_page"], 1)
        self.assertEqual(output["total_results"], 3)

    def test_multiple_value_exclusions_are_or_conditions(self) -> None:
        payload = {"results": [
            {"siren": "1", "categorie_entreprise": "ETI", "siege": {"code_postal": "75001"}},
            {"siren": "2", "categorie_entreprise": "PME", "siege": {"code_postal": "75002"}},
            {"siren": "3", "categorie_entreprise": "GE", "siege": {"code_postal": "75001"}},
            {"siren": "4", "categorie_entreprise": "GE", "siege": {"code_postal": "75003"}},
        ], "page": 1, "total_results": 4}
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search_companies",
            return_value=payload,
        ) as api_search:
            result = CliRunner().invoke(app, [
                "search", "conseil", "--exclude", "categorie_entreprise=PME",
                "--exclude", "siege.code_postal=75001", "--exclude-field", "siege.code_postal",
            ])

        self.assertEqual(result.exit_code, 0)
        api_search.assert_called_once_with({"q": "conseil"}, page=1, per_page=10)
        output = json.loads(result.stdout)
        self.assertEqual(output["results"], [
            {"siren": "4", "categorie_entreprise": "GE", "siege": {}}
        ])
        self.assertEqual(output["excluded_results_on_page"], 3)

    def test_empty_value_exclusion_is_rejected(self) -> None:
        with patch("frco.clients.api_gouv_client.ApiGouvClient.search_companies") as api_search:
            result = CliRunner().invoke(app, ["search", "conseil", "--exclude", "categorie_entreprise="])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("valeur à exclure est vide", result.stderr)
        api_search.assert_not_called()

    def test_invalid_pagination_and_blank_query_are_rejected(self) -> None:
        for args in (["search", "exemple", "--per-page", "26"],
                     ["search", "exemple", "--page", "0"],
                     ["search", "   "]):
            with self.subTest(args=args):
                result = CliRunner().invoke(app, args)
                self.assertNotEqual(result.exit_code, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
