---
name: frco-prospect-list
description: Construire et contrôler une liste de prospection avec frco list, ses filtres NAF, géographiques, d'effectif, de CA et de sites, puis interpréter le CSV et le JSON. Utiliser pour les exports exécutables par le CLI actuel.
---

# Construire une liste de prospection

Depuis le checkout frco, lire `uv run frco list --help` et les règles ci-dessous avant de convertir la demande en options.

```sh
uv run frco list 62.02 --department 75 --active-only
uv run frco list 62.02A --department 75 -o comptes-75.json
uv run frco list 62.02 --department 75 --active-only --output comptes-75.csv
uv run frco list 62.02A --region 11 --employees-min 20 --revenue-min 1000000 --multi-site-only --output comptes-idf.csv
uv run frco list 62.02A --city 75115 --output comptes-paris15.csv
```

Les codes d'exemple sont des critères, pas des noms de villes. `--output` est facultatif : sans cette option, le CLI écrit `prospects.json` dans le dossier courant. Une extension `.json` choisit le JSON UTF-8 et `.csv` le CSV ; les autres extensions sont refusées avant tout appel API. Le tableau JSON normalisé reste écrit sur stdout.

Un fichier de même nom est remplacé après succès. Pour des segments successifs dont les résultats doivent être conservés, donner des noms distincts via `--output` ; ne pas réutiliser le fichier par défaut entre les segments. Le dossier parent doit exister. Le JSON contient une fiche par SIREN ; le CSV une ligne par SIREN.

## Traduire les critères sans en ajouter

- NAF obligatoire : classe rév. 2 `62.02` ou sous-classe `62.02A`. La classe se développe depuis `src/frco/data/naf_rev2_subclasses.csv` : `62.02` donne A et B ; `69.20` donne seulement Z. Ne pas inventer de suffixes. Sections, divisions et groupes ne sont pas acceptés comme argument de `list`.
- `--region`, `--department` prennent des codes INSEE ; `--city` accepte un code de commune ou un nom. Pour une collecte reproductible, résoudre le nom avec un référentiel et employer le code. Le nom seul déclenche une recherche textuelle suivie d'un contrôle local, qui peut manquer des entreprises.
- Le filtrage géographique recherche une présence par établissement, pas nécessairement un siège dans la zone. Ne pas ajouter un contrôle de siège sauf demande explicite. L'activité filtrée est celle de l'unité légale.
- `--active-only` vise l'unité légale active, pas la garantie que tous les sites retournés sont ouverts. Ne pas l'ajouter par défaut si la demande inclut aussi les cessées.
- `--employees-min/max` portent sur les tranches : seules celles entièrement comprises dans l'intervalle sont retenues. Un intervalle « au moins 15 » exclut la tranche 10–19 ; préciser cette perte de précision. Tranche inconnue exclue si un seuil est demandé.
- `--revenue-min/max` portent sur des euros ; le contrôle local utilise le dernier CA publié. Sans filtre de CA, garder les entreprises sans CA. Avec un seuil demandé, les valeurs inconnues ne permettent pas de démontrer l'éligibilité. Un CA absent n'est jamais zéro.
- `--multi-site-only` signifie plus d'un établissement actif. `--establishments-min/max` portent sur le total, ouverts et fermés. Ces filtres s'appliquent localement après collecte et ne réduisent pas le volume côté API.
- `list` n'expose pas `--exclude`, `--exclude-field`, `--include-establishments`, `--parallel` ni `--code-postal`.

## Collecte et couverture

La commande lit toutes les pages annoncées à 25 résultats par page. Elle échoue si le total atteint 10 000, si les métadonnées changent, si des SIREN sont répétés ou si la quantité récupérée diffère du total. Elle ne produit pas de nouvel export partiel dans ces cas. Un ancien fichier au même chemin peut toutefois toujours exister : vérifier le code de sortie avant de le considérer comme le nouvel export.

Pour un découpage, appliquer les règles de `frco-plan-research` si disponible : conserver les critères initiaux et préparer des segments couvrants dans un plan JSON. `list NAF --segments PLAN.json` collecte les segments et fusionne les SIREN dans un seul export. Le plan accepte version 1 et des segments avec id, naf, region, department, city (code INSEE) ; les autres critères sont hérités et ne peuvent pas être modifiés dans le plan. La couverture de la population reste à vérifier par l'agent. Ne pas ajouter un seuil de CA pour passer sous le plafond quand le demandeur n'en voulait pas.

## Lire et vérifier les exports

Le fichier JSON contient le même tableau que stdout, avec le schéma normalisé de `company`. Une recherche vide réussie écrit `[]`. Vérifier que les SIREN sont uniques et que le nombre de fiches correspond à la sortie.

Le CSV est UTF-8 avec BOM pour Excel. Il garde les champs racine du schéma `company` et ajoute les chemins imbriqués (`headquarters.siret`, `representatives[0].name`, etc.). Les cellules parentes conservent les objets/tableaux JSON ; préserver null et liste vide. Les colonnes indexées varient selon les longueurs rencontrées.

Après succès, vérifier le nombre de lignes et l'unicité des SIREN, ainsi que la cohérence avec la longueur du tableau JSON si conservé. Ne pas compter les colonnes parentes et enfants comme des données indépendantes. Conserver les identifiants en texte à l'import Excel. Pour le détail du schéma, lire `src/frco/models/company.py` et `src/frco/formatters/csv_formatter.py`.

Restituer le chemin, le nombre de SIREN uniques, les critères et les limites constatées. L'absence d'un établissement détaillé n'est pas l'absence de présence géographique. Dans `list`, `searched_establishment` est null et la liste détaillée des établissements n'est pas récupérée.
