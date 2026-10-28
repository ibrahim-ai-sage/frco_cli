"""Contrat de sortie de la commande company."""

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from frco.cli.app import app
from frco.services.company_service import CompanyNotFoundError, CompanyService


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "api_response_microsoft_france.json"


class CliTests(unittest.TestCase):
    """Vérifie que stdout reste réservé au JSON."""

    def test_success_has_only_valid_json_on_stdout(self) -> None:
        """Une sortie réussie est directement exploitable par un script."""
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

        with patch("frco.clients.api_gouv_client.ApiGouvClient.search", return_value=payload):
            result = CliRunner().invoke(app, ["company", "32773318400243"])

        self.assertEqual(result.exit_code, 0)
        output = json.loads(result.stdout)
        self.assertEqual(output["searched_establishment"]["siret"], "32773318400243")
        self.assertEqual(result.stderr, "")

    def test_diagnostics_go_to_stderr(self) -> None:
        """Une recherche vide n'émet aucun fragment JSON sur stdout."""
        with patch.object(CompanyService, "find_first", side_effect=CompanyNotFoundError("Aucun résultat.")):
            result = CliRunner().invoke(app, ["company", "000000000"])

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("Aucun résultat.", result.stderr)

    def test_include_establishments_option(self) -> None:
        """L'option demande la liste et expose son éventuelle incomplétude."""
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with patch(
            "frco.clients.api_gouv_client.ApiGouvClient.search", return_value=payload
        ) as search:
            result = CliRunner().invoke(
                app, ["company", "MICROSOFT FRANCE", "--include-establishments"]
            )

        self.assertEqual(result.exit_code, 0)
        search.assert_called_once_with("MICROSOFT FRANCE", establishment_limit=100)
        structure = json.loads(result.stdout)["company_structure"]
        self.assertEqual(len(structure["establishments"]), 10)
        self.assertIs(structure["establishments_complete"], False)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
