---
name: frco-company
description: Consulter et interpréter une fiche entreprise avec frco company par nom, SIREN ou SIRET, y compris siège, établissements, dirigeants, effectifs et finances. Utiliser pour une entreprise précise, pas une collecte de marché.
---

# Consulter une entreprise

Exécuter depuis le checkout frco identifié par `pyproject.toml` et `README.md`. Vérifier `uv run frco company --help` si l'interface a changé.

```sh
uv run frco company "Microsoft France"
uv run frco company 327733184
uv run frco company 32773318400243 --include-establishments
```

La commande renvoie le premier résultat en JSON normalisé. Pour un nom ambigu, demander un SIREN/SIRET ou des précisions permettant de vérifier l'identité avant de conclure. Ne pas présenter le premier homonyme comme une correspondance certaine.

## Lire la fiche sans changer son sens

- Conserver SIREN et SIRET en chaînes, avec leurs zéros initiaux.
- `headquarters.siret` désigne le siège. `searched_establishment` désigne le SIRET demandé s'il est attesté par la réponse ; il peut être null. Ne pas intervertir les adresses ni inférer un siège depuis le SIRET recherché.
- `administrative_status` concerne l'unité légale : A active, C cessée. Dans le détail des établissements, A signifie actif et F fermé.
- `employee_band` est une tranche pour l'unité légale avec année de référence ; ce n'est pas un effectif exact. Les finances normalisées proviennent également de l'unité légale.
- `representatives` comprend dirigeants, commissaires aux comptes et autres acteurs. Lire `category` (`leader`, `auditor`, `other`) et le rôle avant de décrire quelqu'un comme dirigeant.
- `revenue_history` est trié du plus récent au plus ancien, en euros numériques. `revenue_growth` ne compare que les deux derniers exercices publiés consécutifs, avec CA de départ strictement positif. Un null n'indique ni stagnation ni baisse.
- CA absent : inconnu/non disponible, jamais zéro. Ne pas affirmer qu'il est confidentiel sans preuve ; la non-publication n'est qu'une cause possible.
- `metadata.retrieved_at` est la date de récupération en UTC, pas la date de mise à jour de l'entreprise.

## Interpréter les établissements

Sans `--include-establishments`, la liste et son indicateur d'exhaustivité sont null. Avec l'option, le CLI récupère les établissements disponibles, avec une éventuelle recherche complémentaire par nom pour le même SIREN.

`total_establishments` compte tous les établissements ; `active_establishments` compte les ouverts. `is_multi_site` signifie plus d'un SIRET actif, pas plusieurs adresses distinctes. Compteur absent = inconnu.

`establishments: null` signifie non récupéré ; `[]` signifie récupéré mais vide. `establishments_complete: false` indique une liste insuffisante au regard du total ; null signifie non vérifiable. Dans cette version, ne pas annoncer une liste exhaustive, même si le nombre retourné égale le compteur. La pagination des entreprises n'est pas celle de leurs établissements.

Pour le schéma exact, lire `src/frco/models/company.py` et la section de structure du README du checkout. Résumer la fiche en conservant les années et les incertitudes ; ne pas inventer une option de sortie Markdown, absente de cette commande.
