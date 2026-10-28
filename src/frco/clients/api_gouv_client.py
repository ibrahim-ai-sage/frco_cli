"""Accès HTTP à l'API Recherche d'entreprises."""

from typing import Any, Mapping
import time

import requests


API_URL = "https://recherche-entreprises.api.gouv.fr/search"


class ApiGouvError(Exception):
    """Signale une réponse ou une connexion API inutilisable."""


class ApiGouvClient:
    """Effectue les requêtes vers l'API Recherche d'entreprises."""

    def __init__(self, timeout: float = 10.0) -> None:
        """Configure les délais de connexion et de lecture HTTP.

        Args:
            timeout: Délai en secondes pour la connexion et la lecture HTTP.
        """
        self.timeout = timeout
        self._last_request_at: float | None = None

    def search(self, query: str, *, establishment_limit: int | None = None) -> dict[str, Any]:
        """Recherche une entreprise avec la requête saisie telle quelle.

        Args:
            query: Nom, SIREN ou SIRET transmis dans le paramètre ``q``.
            establishment_limit: Nombre maximal d'établissements connexes
                demandés dans la réponse, si la liste détaillée est requise.

        Returns:
            Corps JSON de la réponse API.

        Raises:
            ApiGouvError: En cas d'erreur réseau, HTTP ou de réponse JSON invalide.
        """
        params: dict[str, str | int] = {"q": query, "per_page": 1}
        if establishment_limit is not None:
            params["limite_matching_etablissements"] = establishment_limit
        return self._get(params)

    def search_companies(
        self, filters: Mapping[str, str | int], *, page: int, per_page: int = 25
    ) -> dict[str, Any]:
        """Récupère une page d'entreprises selon des filtres API.

        Args:
            filters: Paramètres de recherche de l'API.
            page: Numéro de page, à partir de 1.
            per_page: Nombre de résultats, limité à 25 par l'API.

        Returns:
            Corps JSON de la page.
        """
        return self._get({**filters, "page": page, "per_page": per_page})

    def _get(self, params: Mapping[str, str | int]) -> dict[str, Any]:
        """Exécute une requête GET et valide la réponse JSON."""
        if self._last_request_at is not None:
            delay = 0.16 - (time.monotonic() - self._last_request_at)
            if delay > 0:
                time.sleep(delay)
        try:
            self._last_request_at = time.monotonic()
            response = requests.get(
                API_URL,
                params=params,
                headers={"Accept": "application/json", "User-Agent": "frco/0.1.0"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise ApiGouvError("L'API ne répond pas dans le délai imparti.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "inconnu"
            raise ApiGouvError(f"L'API a répondu avec le statut HTTP {status}.") from exc
        except requests.exceptions.JSONDecodeError as exc:
            raise ApiGouvError("L'API a renvoyé une réponse JSON invalide.") from exc
        except requests.RequestException as exc:
            raise ApiGouvError(f"Impossible de contacter l'API : {exc}") from exc

        if not isinstance(payload, dict):
            raise ApiGouvError("La réponse JSON de l'API n'est pas un objet.")
        return payload
