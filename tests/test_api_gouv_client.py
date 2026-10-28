"""Paramètres HTTP de la recherche et de sa vue détaillée."""

import unittest
from unittest.mock import patch

from frco.clients.api_gouv_client import API_URL, ApiGouvClient


class ApiGouvClientTests(unittest.TestCase):
    """Vérifie que la valeur recherchée reste intacte."""

    def test_search_keeps_query_unchanged(self) -> None:
        """La recherche standard utilise le SIRET fourni tel quel."""
        with patch("frco.clients.api_gouv_client.requests.get") as get:
            get.return_value.json.return_value = {"results": []}
            ApiGouvClient(timeout=4).search("32773318400243")

        self.assertEqual(get.call_args.args, (API_URL,))
        self.assertEqual(get.call_args.kwargs["params"], {
            "q": "32773318400243", "per_page": 1
        })
        self.assertEqual(get.call_args.kwargs["timeout"], 4)

    def test_detailed_search_requests_api_limit(self) -> None:
        """La liste détaillée demande explicitement jusqu'à 100 entrées."""
        with patch("frco.clients.api_gouv_client.requests.get") as get:
            get.return_value.json.return_value = {"results": []}
            ApiGouvClient().search("MICROSOFT FRANCE", establishment_limit=100)

        self.assertEqual(get.call_args.kwargs["params"], {
            "q": "MICROSOFT FRANCE",
            "per_page": 1,
            "limite_matching_etablissements": 100,
        })

    def test_filtered_search_passes_naf_and_pagination(self) -> None:
        """La liste utilise les filtres API et conserve la taille de page 25."""
        with patch("frco.clients.api_gouv_client.requests.get") as get:
            get.return_value.json.return_value = {"results": []}
            ApiGouvClient().search_companies(
                {"activite_principale": "62.02A,62.02B", "departement": "75"},
                page=2,
            )

        self.assertEqual(get.call_args.kwargs["params"], {
            "activite_principale": "62.02A,62.02B",
            "departement": "75",
            "page": 2,
            "per_page": 25,
        })

if __name__ == "__main__":
    unittest.main()
