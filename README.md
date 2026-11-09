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

## Listes de prospection

```sh
uv run frco list 62.02A --department 75 --active-only
uv run frco list 62.02A --department 75 -o comptes.json
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

La commande lit toutes les pages annoncées par l'API et crée par défaut
`prospects.json` dans le dossier courant, en UTF-8. `--output` (`-o`) est
facultatif : une extension `.json` choisit le JSON et `.csv` le CSV ; toute
autre extension est refusée avant l'appel API. Un fichier de même nom est
remplacé après une collecte et une écriture réussies.

Le tableau JSON reste également écrit sur stdout. Chaque objet du tableau
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
diagnostic sur stderr et n'écrit aucun export partiel. Décomposez la recherche
avec un plan de segments pour conserver le périmètre, plutôt que d'ajouter des
seuils qui pourraient exclure des entreprises. Les [paramètres et limites de l'API](https://recherche-entreprises.api.gouv.fr/docs/)
font autorité pour la recherche.

### Collecter plus de 10 000 entreprises avec un plan

`--segments` permet à une skill ou à l'utilisateur de définir les sous-recherches,
puis au CLI de les collecter en un seul lancement et de réunir leurs SIREN :

```sh
uv run frco list 62.02 --department 75 --segments examples/segments-naf-62.02.json -o comptes-75.json
```

Le plan d'exemple découpe la classe `62.02` en ses deux sous-classes. Un plan
peut aussi définir des communes par code INSEE, par exemple :

```json
{
  "version": 1,
  "segments": [
    {"id": "paris15", "city": "75115"},
    {"id": "paris16", "city": "75116"}
  ]
}
```

Ce second exemple couvre uniquement ces deux arrondissements, pas tout Paris.
Les seules propriétés acceptées dans un segment sont `id`, `naf`, `region`,
`department` et `city`. L'identifiant est obligatoire et unique. Les autres
critères sont hérités de la commande. Un segment ne peut pas remplacer une
contrainte géographique initiale par une autre ni sortir des NAF initiaux.
Il peut ajouter un niveau plus fin : `--department 75` reste transmis lorsque
le segment ajoute `city`. Les seuils d'effectif, de CA et les autres critères
ne peuvent pas être modifiés dans le plan. Sans filtre financier demandé,
les entreprises au CA inconnu restent incluses.

Tout le plan est validé avant le premier appel API. Les segments sont ensuite
collectés séquentiellement avec le même client et son délai entre appels.
Chaque segment doit rester sous 10 000 résultats ; si une feuille est encore
plafonnée, le message d'erreur l'identifie pour permettre à l'agent de la
subdiviser. En cas d'échec, le fichier final existant est conservé.

Le nombre total de SIREN uniques peut dépasser 10 000. Les doublons entre
segments sont fusionnés en conservant la fiche entière récupérée le plus
récemment, sans fabriquer une liste exhaustive d'établissements. Le bilan
est écrit sur stderr ; stdout et le fichier conservent le schéma habituel.
Les référentiels NAF sont mis en cache pendant l'exécution pour éviter de
relire les mêmes fichiers pour chaque fiche.

Le CLI valide l'exécution des segments, mais ne déduit pas leurs descendants
et ne prouve pas que la liste fournie couvre tout le marché demandé. Cette
vérification reste du ressort de la skill et du référentiel utilisé. Il n'y a
pas encore de collecte parallèle ni de reprise automatique des segments réussis.

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

## Skills pour les agents

Les sources des quatre skills sont conservées dans [`skills/`](skills/). Elles
décrivent l'interface actuelle du CLI et les règles métier à respecter :

| Skill | Utilisation |
|---|---|
| [`frco-cli`](skills/frco-cli/SKILL.md) | Prise en main, installation et choix de commande |
| [`frco-company`](skills/frco-company/SKILL.md) | Fiche entreprise et interprétation des données |
| [`frco-prospect-list`](skills/frco-prospect-list/SKILL.md) | Filtres de prospection et exports CSV/JSON |
| [`frco-plan-research`](skills/frco-plan-research/SKILL.md) | Relations entre champs, découpage et couverture |

Une fois installées dans le dossier personnel de skills de l'agent, elles
peuvent être invoquées explicitement, par exemple :

```text
Utilise $frco-company pour consulter Microsoft France.
Utilise $frco-prospect-list pour exporter les entreprises actives du NAF 62.02 dans le 75.
Utilise $frco-plan-research pour décomposer une recherche sur le département 75.
```

La planification privilégie un découpage géographique initial, conserve les
critères demandés et les valeurs inconnues pertinentes, puis contrôle chaque
segment. Le CLI exécute et fusionne les plans via `list --segments` ; le
parallélisme et les recherches structurées sans NAF ne sont pas intégrés.
La [cartographie des champs](docs/research-field-map.md) détaille les relations
et les vérifications restant à établir.

## Tests

```sh
uv run python -m unittest discover -s tests -v
```
