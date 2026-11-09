---
name: frco-cli
description: Prendre en main le CLI Python frco, choisir entre company et list, vérifier son installation et diagnostiquer son exécution. Utiliser pour les demandes portant sur ce CLI français, pas pour les CLI en général.
---

# Prendre en main frco

`frco` interroge l'API Recherche d'entreprises et produit des fiches ou des listes. Les commandes décrites ici correspondent à la version locale 0.1.0 ; vérifier `--help` et le code du checkout si leur interface évolue.

## Trouver et exécuter le projet

Dans le workspace, chercher `pyproject.toml` avec `project.name = "frco"`, puis lire `README.md`. Ne pas exécuter depuis le dossier de la skill. Si aucun checkout n'est accessible, demander son emplacement plutôt que d'inventer un chemin ou d'installer un homonyme.

Depuis le checkout :

```sh
uv sync
uv run frco --help
uv run frco company --help
uv run frco list --help
```

Python >= 3.12 et uv sont nécessaires à ce mode d'installation. Si l'environnement `.venv` fonctionne déjà, éviter une synchronisation inutile. Sous Windows, `.venv\Scripts\frco.exe --help` permet de tester l'entrée installée sans passer par le cache uv.

## Choisir la commande

| Besoin | Commande | Sortie |
|---|---|---|
| Une fiche par nom, SIREN ou SIRET | `company QUERY` | Premier résultat normalisé, JSON |
| Prospection par classe/sous-classe NAF | `list NAF [--output PATH]` | Fichier prospects.json par défaut, CSV si extension .csv, et tableau JSON sur stdout |

Pour une opération spécialisée, utiliser la skill correspondante si elle est installée : `frco-company`, `frco-prospect-list`, `frco-plan-research`. Le CLI peut être utilisé directement si elle n'est pas disponible.

## Limites qui changent les décisions

- Les seules commandes disponibles sont `company` et `list`. Ne pas inventer de commande de recherche paginée ou d’options `--all`, `--parallel` ou `--format`.
- `list` exige une classe ou sous-classe NAF rév. 2. Il n'existe pas de commande générale « toutes les entreprises d'un département ».
- Les erreurs vont sur stderr avec un code non nul. Un échec n'est pas une liste vide ; conserver le diagnostic.
- `company` renvoie une fiche normalisée ; `list` renvoie un tableau de ces fiches et écrit `prospects.json` par défaut. `--output` est facultatif ; `.json` ou `.csv` choisit le format. Un fichier de même nom est remplacé après succès.
- `list --segments PLAN.json` exécute un découpage explicite et fusionne les SIREN. La skill `frco-plan-research` décrit le format et les contrôles de couverture ; aucun découpage automatique ni parallélisme n'est intégré.
- Une skill explique la stratégie, elle ne crée pas d'options manquantes. Ne pas contourner une lacune par un script/API ad hoc sans demande autorisant cette extension.

## Diagnostic proportionné

Vérifier le répertoire, `--help`, l'interpréteur et les dépendances avant de modifier du code. Les problèmes d'accès au cache uv ou au dossier temporaire Windows sont distincts d'un bug métier ; utiliser au besoin un cache/dossier temporaire autorisé, limité au processus. Ne pas modifier les réglages globaux Git ou les permissions pour une simple consultation.

Pour vérifier une modification de code du projet : `uv run python -m unittest discover -s tests`. Les tests utilisent des réponses simulées ; leur succès ne prouve pas la disponibilité de l'API. Ne pas annoncer un appel réel sans l'avoir exécuté.
