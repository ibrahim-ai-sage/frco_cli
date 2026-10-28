# frco

CLI minimal pour rechercher une entreprise française avec l'[API Recherche
d'entreprises](https://recherche-entreprises.api.gouv.fr/docs/).

## Installation

Python 3.12 ou plus récent et `uv` sont requis. Depuis ce dossier :

```sh
uv sync
```

## Utilisation

```sh
uv run frco company "Microsoft France"
uv run frco company 327733184
uv run frco company 32773318400243
uv run frco company 327733184 --include-establishments
```

L'argument est transmis tel quel dans `q`. La commande affiche le premier
résultat en JSON sur stdout. Les erreurs réseau, HTTP, de réponse ou l'absence
de résultat sont signalées sur stderr avec un code de sortie non nul.

## Recherche simple

```sh
uv run frco search "Microsoft France"
uv run frco search 327733184 --page 2 --per-page 25
uv run frco search "conseil" --exclude ETI
uv run frco search "conseil" --exclude categorie_entreprise=PME
uv run frco search "Microsoft France" --exclude-field dirigeants --exclude-field siege.adresse
```

`search` transmet la requête telle quelle dans `q` et affiche la réponse JSON
de l'API sur stdout, avec les résultats et les métadonnées de pagination.
La commande demande 10 résultats par page par défaut. `--per-page` accepte de 1
à 25 résultats. Une recherche sans résultat renvoie une liste `results` vide.
Les erreurs sont affichées sur stderr avec un code de sortie non nul.
`--exclude` retire des entreprises **après** l'appel API. `--exclude ETI`
retire celles dont `categorie_entreprise` vaut `ETI` ; la syntaxe
`--exclude champ=valeur` accepte d'autres champs et peut être répétée. Plusieurs
exclusions sont combinées avec « ou ». La recherche reste paginée par l'API :
`total_results` et `total_pages` décrivent les résultats **avant** exclusion,
et `excluded_results_on_page` indique combien ont été retirés de la page reçue.
La commande ne recharge pas la page pour compenser les exclusions.

`--exclude-field` retire un champ du JSON affiché, sans retirer l'entreprise.
L'option peut être répétée. Les chemins sont relatifs à chaque entreprise de
`results` ; par exemple, `siege.adresse` retire l'adresse du siège et
`dirigeants.nom` retire le nom de chaque dirigeant. Toutes les exclusions sont
appliquées localement après la réponse de l'API ; aucun critère d'exclusion
n'est ajouté à la requête.

## Listes de prospection

```sh
uv run frco list 62.02A --department 75 --active-only --output prospects.csv
uv run frco list 62.02 --region 11 --employees-min 20 --revenue-min 1000000 --multi-site-only -o comptes.csv
uv run frco list 69.20 --city Paris --revenue-min 10000000 --establishments-min 2 -o paris.csv
uv run frco list 62.02A --city 75115 --employees-max 49 --revenue-max 5000000 -o quartier.csv
```

`list` exige une sous-classe NAF rév. 2 (`62.02A`) ou une classe (`62.02`).
La classe est développée en toutes ses sous-classes figurant dans la référence
[Insee NAF rév. 2](https://www.insee.fr/fr/metadonnees/nafr2/classe/62.02).
La classe `62.02` donne `62.02A` et `62.02B`. La classe
[69.20](https://www.insee.fr/fr/metadonnees/nafr2/classe/69.20) donne seulement
`69.20Z` dans cette nomenclature : `69.20A` n'y existe pas.

La commande lit toutes les pages annoncées par l'API, exporte un CSV UTF-8
dans `--output`, puis écrit un tableau JSON sur stdout. Chaque objet du tableau
utilise exactement le schéma de `frco company`; `searched_establishment` est
`null`, car une liste ne recherche pas un SIRET précis. Le CSV contient une
ligne par SIREN. Il conserve les champs racine de cette même fiche et ajoute
une colonne pour chaque champ imbriqué :

```text
name,siren,headquarters,searched_establishment,company_structure,administrative_status,naf_code,naf_label,activity_section,activity_section_label,employee_band,representatives,revenue_history,revenue_growth,metadata
```

Par exemple, `searched_establishment` et `company_structure` restent des
colonnes, suivies de `company_structure.total_establishments`,
`company_structure.active_establishments`, `company_structure.is_multi_site`,
`company_structure.establishments` et
`company_structure.establishments_complete` : sept colonnes au total pour cet
extrait. Le siège est aussi décliné en `headquarters.siret`,
`headquarters.address`, `headquarters.city` et `headquarters.postal_code`.
Les tableaux sont déclinés par position, par exemple
`representatives[0].name` ou `revenue_history[0].revenue_eur`. Le nombre de
colonnes indexées suit la plus longue liste rencontrée dans l'export ; une
position absente reste vide pour l'entreprise concernée.

Les colonnes parentes conservent le JSON complet pour préserver les objets,
les tableaux et la différence entre `null` et `[]`. Chaque champ enfant est
aussi accessible directement dans sa propre colonne. Le CSV est encodé en
UTF-8 avec marqueur BOM pour une ouverture directe dans Excel.

Cette version du CSV remplace les anciennes colonnes aplaties
`headquarters_siret`, `revenue_latest_amount`, `is_multi_site`, etc. Leurs
valeurs sont accessibles dans les colonnes de chemin correspondantes, par
exemple `headquarters.siret`, `revenue_history[0].revenue_eur` et
`company_structure.is_multi_site`.

`--region` et `--department` prennent des codes INSEE et filtrent les
entreprises ayant un établissement dans la zone ; le siège peut être ailleurs.
`--city` accepte un code INSEE de commune, transmis comme `code_commune`, ou
un nom de ville. Pour un nom, l'API effectue une recherche textuelle puis le
CLI vérifie la commune des établissements retournés : cette recherche textuelle
peut manquer des comptes. Un code de commune est préférable pour une sélection
géographique reproductible. Pour Paris, Lyon et Marseille, le code INSEE d'un
arrondissement peut être nécessaire.

Les seuils d'effectif portent sur les **tranches** publiées pour l'unité
légale : une tranche n'est retenue que si elle est entièrement dans
l'intervalle demandé. Une tranche inconnue ou chevauchant une borne est
exclue. Les seuils de CA portent sur le dernier exercice disponible.
`--multi-site-only` signifie strictement plus d'un établissement actif ;
`--establishments-min` et `--establishments-max` portent sur le total des
établissements. Les valeurs absentes ne satisfont pas ces filtres.

L'API plafonne certaines recherches larges à 10 000 résultats. Si ce plafond
est atteint, ou si les pages sont incohérentes, la commande échoue avec un
diagnostic sur stderr et n'écrit aucun CSV partiel. Ajoutez des critères pour
réduire la recherche. Les [paramètres et limites de l'API](https://recherche-entreprises.api.gouv.fr/docs/)
font autorité pour la recherche.

L'API fournit séparément l'unité légale, son `siege` et les
`matching_etablissements`. `headquarters.siret` est la seule référence au
SIRET du siège ; le siège est repris seulement lorsque la réponse ne le
contredit pas. Pour un argument
de 14 chiffres, `searched_establishment` correspond à l'établissement dont
le SIRET concorde exactement avec celui demandé. Il reste `null` si cet
établissement ne figure pas dans la réponse. Pour un nom ou un SIREN,
`searched_establishment` est `null`. Tous les identifiants restent des chaînes.

`company_structure` reprend les compteurs fournis par l'API :
`total_establishments` compte tous les établissements rattachés au SIREN
et `active_establishments` ceux qui sont ouverts. `is_multi_site` vaut
`true` quand plus d'un établissement est actif, `false` sinon, ou
`null` si le compteur actif manque. Il s'agit d'un indicateur fondé sur les
SIRET actifs, pas d'un décompte d'adresses distinctes. Un compteur inconnu
reste `null` et ne devient jamais zéro.

Par défaut, `establishments` et `establishments_complete` valent `null`.
Avec `--include-establishments`, chaque établissement disponible contient
son `siret`, son `administrative_status` (code `A` « Actif » ou `F`
« Fermé »), sa `city` et `is_headquarters`. La liste est dédupliquée par
SIRET. `establishments: null` signifie que la liste n'a pas été récupérée ;
`establishments: []` signifie qu'elle a été récupérée mais qu'elle est vide.
`establishments_complete` vaut `false` si le nombre de SIRET retournés est
inférieur au total indiqué par la source. Il vaut `null` si l'exhaustivité
n'est pas vérifiable, même lorsque les deux nombres sont égaux : une seule
page de résultats ne prouve pas que tous les établissements sont présents.
`true` est réservé à une liste exhaustive vérifiée ; le mode actuel ne
dispose pas d'une telle garantie de pagination. Les champs de pagination
`page` et `total_pages` de la réponse concernent les résultats d'entreprises,
pas la liste des établissements d'un SIREN. L'API limite la liste incluse à 100
établissements par réponse ; une recherche directe par SIREN ou SIRET peut
renvoyer moins d'établissements que le total. Dans ce cas, le CLI tente une
recherche complémentaire par nom et ne retient que le résultat avec le même
SIREN. Les compteurs agrégés proviennent toujours de la première réponse.

`administrative_status` contient le code et le libellé de l'unité légale :
`A` signifie « Active » et `C` « Cessée », selon la
[documentation de l'API](https://recherche-entreprises.api.gouv.fr/docs/).
Un code inconnu conserve un libellé `null`.

`naf_code` et `naf_label` gardent le code et son libellé. Lorsque le libellé
manque dans l'API, il est résolu avec la nomenclature NAF rév. 2 de l'Insee.
`activity_section` et `activity_section_label` gardent la section et son
libellé. `employee_band` contient le code de tranche, son libellé et l'année
de référence ; un code inconnu conserve un libellé `null`. Les références
locales de [sous-classes](https://www.insee.fr/fr/statistiques/fichier/2120875/naf2008_liste_n5.dbf),
de [sections](https://www.insee.fr/fr/statistiques/fichier/2120875/naf2008_liste_n1.dbf)
et de [tranches d'effectif](https://www.insee.fr/fr/information/1896441)
proviennent de l'Insee.

`employee_band` est lu dans `tranche_effectif_salarie` à la racine du
résultat de l'unité légale identifiée par `siren`, et `revenue_history`
dans son champ racine `finances`. Les champs homonymes présents dans
`siege` ou `matching_etablissements` ne sont pas utilisés pour ces deux
données.

`representatives` reprend tous les acteurs du champ `dirigeants` de l'API.
Chaque entrée conserve `name`, `role` et `entity_type`. `category` vaut
`leader` pour un rôle de direction reconnu, `auditor` pour un commissaire
aux comptes et `other` si le rôle ne permet pas une classification fiable.
Les noms des personnes reprennent `prenoms` et `nom` tels que fournis par
l'API ; un nom source contenant des parenthèses est conservé.

`revenue_history` conserve les exercices du plus récent au plus ancien, avec
`year` et `revenue_eur` numériques. `revenue_growth` compare uniquement
les deux derniers CA publiés s'ils couvrent des années consécutives et si
le CA de départ est strictement positif. Le pourcentage vaut
`(CA final - CA initial) / CA initial × 100`. Sinon l'objet vaut `null`.
Les montants lisibles tels que « 5,34 M€ » relèvent du formateur Markdown ;
ils ne sont pas insérés dans le JSON.

`metadata.source` identifie l'API interrogée. `metadata.retrieved_at`
indique l'instant de récupération en UTC au format ISO 8601 ; ce n'est pas
une date de mise à jour des données de l'entreprise.

### Exemple de structure

```json
{
  "name": "EXEMPLE SAS",
  "siren": "123456789",
  "headquarters": {
    "siret": "12345678900011",
    "address": "1 RUE EXEMPLE 75001 PARIS",
    "city": "PARIS",
    "postal_code": "75001"
  },
  "searched_establishment": null,
  "company_structure": {
    "total_establishments": 3,
    "active_establishments": 2,
    "is_multi_site": true,
    "establishments": null,
    "establishments_complete": null
  },
  "administrative_status": {"code": "A", "label": "Active"},
  "naf_code": "62.02A",
  "naf_label": "Conseil en systèmes et logiciels informatiques",
  "activity_section": "J",
  "activity_section_label": "Information et communication",
  "employee_band": {"code": "11", "label": "10 à 19 salariés", "year": 2024},
  "representatives": [
    {"name": "CAMILLE EXEMPLE", "role": "Président de SAS",
     "entity_type": "personne physique", "category": "leader"}
  ],
  "revenue_history": [
    {"year": 2024, "revenue_eur": 1200000},
    {"year": 2023, "revenue_eur": 1000000}
  ],
  "revenue_growth": {"from_year": 2023, "to_year": 2024, "percent": 20.0},
  "metadata": {
    "source": "API Recherche d'entreprises",
    "retrieved_at": "2026-10-21T12:00:00Z"
  }
}
```

Cet exemple illustre le schéma et ne représente pas une entreprise réelle.

Pour une recherche par SIRET d'un autre établissement, les deux objets
d'adresses sont distincts. Extrait d'une réponse pour `32773318400243` :

```json
{
  "siren": "327733184",
  "headquarters": {
    "siret": "32773318400516",
    "address": "37/45 37 QUAI DU PRESIDENT ROOSEVELT 92130 ISSY-LES-MOULINEAUX",
    "city": "ISSY-LES-MOULINEAUX",
    "postal_code": "92130"
  },
  "searched_establishment": {
    "siret": "32773318400243",
    "address": "COURTABOEUF BAT 1 OPENSPAC 18 AVENUE DU QUEBEC 91140 VILLEBON-SUR-YVETTE",
    "city": "VILLEBON-SUR-YVETTE",
    "postal_code": "91140"
  }
}
```

Avec `--include-establishments`, la section contient par exemple :

```json
{
  "total_establishments": 2,
  "active_establishments": 1,
  "is_multi_site": false,
  "establishments": [
    {
      "siret": "12345678900011",
      "administrative_status": {"code": "A", "label": "Actif"},
      "city": "PARIS",
      "is_headquarters": true
    },
    {
      "siret": "12345678900029",
      "administrative_status": {"code": "F", "label": "Fermé"},
      "city": "LYON",
      "is_headquarters": false
    }
  ],
  "establishments_complete": null
}
```

Cette seconde illustration est également fictive.

### Changements du schéma

Les consommateurs JSON doivent lire le SIRET du siège uniquement dans
`headquarters.siret`. Les anciens champs racine `siret` et
`headquarters_siret`, ainsi que `company_structure.headquarters_siret`,
sont supprimés. Les champs d'adresse racine passent dans `headquarters`.
Il faut remplacer `status` par `administrative_status` et `leaders` par
`representatives`. Dans `revenue_history`, `revenue_eur` remplace
`revenue`. `revenue_growth` remplace `revenue_growth_percent` et
`is_growing`.

Cette version ajoute `company_structure` aux réponses. Les scripts qui
valident strictement les clés racine doivent accepter ce nouveau champ.

## Tests

```sh
uv run python -m unittest discover -s tests -v
```
