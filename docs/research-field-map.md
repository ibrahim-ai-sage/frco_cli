# Relations entre champs et décomposition des recherches

État de travail au 30 octobre 2026. Base pour de futures skills de recherche ; aucune stratégie automatique n'est encore ajoutée au CLI.

## Objectif et périmètre

Décrire les champs du CLI actuel et les principales extensions utiles pour décomposer une recherche. Ce document n'est pas un inventaire exhaustif de tous les paramètres de l'API. Il sépare les faits documentés, les comportements du code local et les stratégies proposées à valider.

Le découpage doit conserver la population demandée : ajouter un filtre arbitraire peut réduire le volume en perdant des comptes. La réunion des sous-recherches doit couvrir le périmètre initial, avec déduplication et traitement explicite des données inconnues.

## 1. Entités et relations

| Relation | Nature | Conséquence pour la recherche |
|---|---|---|
| Unité légale identifiée par SIREN → établissements identifiés par SIRET | Un à plusieurs | Une recherche de comptes se déduplique par SIREN ; une recherche de sites par SIRET. |
| Unité légale → siège | Établissement particulier | « Siège dans la zone » et « au moins un établissement dans la zone » sont deux demandes différentes. |
| Établissement → localisation | Localisation à une date donnée | Les partitions géographiques peuvent se chevaucher une fois les résultats ramenés au SIREN. |
| Région → départements → communes | Inclusion administrative, avec un millésime et des cas territoriaux particuliers | Résoudre les descendants depuis un référentiel, pas depuis un préfixe supposé. |
| Paris, Lyon, Marseille → arrondissements municipaux | Cas géographique particulier | Ne pas confondre arrondissement municipal et arrondissement départemental. Valider les codes acceptés par l'API. |
| Code postal ↔ commune | Correspondance plusieurs-à-plusieurs | Un code postal n'est pas un niveau universel inférieur à la commune. |
| EPCI ↔ communes | Appartenance à une intercommunalité | Branche de zonage distincte ; ne pas insérer automatiquement entre département et commune. |
| Section NAF → division → groupe → classe → sous-classe | Hiérarchie de nomenclature | Développer les codes avec un référentiel versionné. |
| Catégorie d'entreprise, tranche d'effectif, CA | Dimensions distinctes | PME/ETI/GE ne sont pas les enfants de tranches d'effectif ni d'intervalles de CA. |

Sources : définitions Insee de l'[unité légale](https://www.insee.fr/fr/metadonnees/definition/c1044), de l'[établissement](https://www.insee.fr/fr/metadonnees/definition/c1377) et de l'[entreprise statistique](https://www.insee.fr/fr/metadonnees/definition/c1496) ; [géographie administrative](https://www.insee.fr/fr/information/8064273) ; [codes INSEE et codes postaux](https://www.insee.fr/fr/information/1302169?question=quel-est-le-code-insee-de-ma-commune) et [correspondances La Poste](https://www.data.gouv.fr/datasets/base-officielle-des-codes-postaux) ; [structure NAF rév. 2](https://www.insee.fr/fr/information/3281579).

## 2. Matrice des champs utilisables

Les noms dans la colonne API sont les paramètres de requête, pas nécessairement les noms des champs de sortie JSON. « Disponible » décrit le CLI local inspecté, pas une capacité future.

| Dimension | Champ CLI / API | Granularité et relation | Décomposition envisagée | État local / limites |
|---|---|---|---|---|
| Identité | argument de `company` / `q` | Nom, SIREN ou SIRET | Résolution d'identité, pas partition de marché | Disponible ; `company` prend le premier résultat. |
| Région | `list --region` / `region` | Zone englobante | Départements du référentiel | Disponible ; référentiel de décomposition absent. |
| Département | `list --department` / `departement` | Zone englobante | Communes ; traitement spécifique de Paris | Disponible ; décomposition absente. |
| Commune | `list --city CODE` / `code_commune` | Zone administrative | Autres dimensions si encore trop large | Disponible ; préférer le code au nom pour la collecte. |
| Nom de ville | `list --city NOM` / `q`, puis contrôle local | Recherche textuelle et comparaison des lieux retournés | Résoudre d'abord en code | Disponible, mais ce mode peut manquer des comptes. |
| Code postal | Aucun / `code_postal` | Zonage postal | Codes issus d'une table de correspondance | Pas exposé par le CLI ; couverture à vérifier avant utilisation. |
| EPCI | Aucun / `epci` | Zonage intercommunal | Communes membres | Pas exposé ; la documentation API signale des limites de fiabilité. |
| Activité | argument NAF de `list` / `activite_principale` | Activité principale de l'unité légale | Classe → toutes ses sous-classes ; extensions aux niveaux supérieurs | Classe et sous-classe rév. 2 disponibles. |
| Section d'activité | Aucun / `section_activite_principale` | Parent de divisions NAF | Développer vers les sous-classes officielles | Section présente en sortie ; filtre non exposé. |
| Effectif | `list --employees-min/max` / `tranche_effectif_salarie` | Tranche, pas effectif exact | Ensemble de codes de tranche | Disponible ; seules les tranches entièrement dans l'intervalle sont retenues. |
| Catégorie | Aucun / `categorie_entreprise` côté API | PME, ETI, GE | Énumération des catégories seulement si les inconnus sont traités | Filtre de catégorie non exposé par le CLI. |
| CA | `list --revenue-min/max` / `ca_min`, `ca_max` | Montant et exercice de référence | Intervalles couvrant le domaine initial | Disponible ; le CLI contrôle le dernier CA publié ; absents exclus si seuil demandé. |
| Statut | `list --active-only` / `etat_administratif` | État de l'unité légale | Valeurs explicites avec résidu éventuel | Actives seules disponible ; statut des établissements distinct. |
| Multi-site | `list --multi-site-only` / aucun filtre envoyé | Plus d'un établissement actif | Filtre local, pas axe de partition serveur actuel | Disponible après collecte. |
| Nombre de sites | `list --establishments-min/max` / aucun filtre envoyé | Total des établissements du SIREN | Filtre local | Ne réduit pas le volume interrogé côté API. |
| Représentants | `representatives` en sortie | Plusieurs acteurs et rôles par unité légale | Aucun découpage exhaustif établi | Présent dans les fiches ; retirer les champs ou acteurs n'est pas partitionner les entreprises. |
| Historique / croissance | `revenue_history`, `revenue_growth` en sortie | Exercices ordonnés et comparaison dérivée | Aucun filtre serveur actuel pour la croissance | Ne pas assimiler un champ calculé à un paramètre API. |
| Projection | Aucune option CLI | Champs du JSON | Sans effet sur la population recherchée | Retrait de champs non exposé par le CLI. |
| Pagination | Automatique dans `list` | Pages d'un même ensemble | Parcours, pas subdivision métier | `list` parcourt les pages et refuse un total >= 10 000. |

Référence des paramètres et de leur portée : [documentation API](https://recherche-entreprises.api.gouv.fr/docs/). Elle précise notamment que les filtres géographiques visent les établissements, que l'activité principale vise l'unité légale, et qu'une recherche directe par SIREN/SIRET ignore les autres filtres. Ne pas utiliser ce mode pour vérifier qu'un identifiant satisfait une zone.

Preuves locales : `src/frco/cli/company.py`, `src/frco/cli/prospect_list.py`, `src/frco/services/prospect_list_service.py`, `src/frco/services/activity_reference.py`, `src/frco/clients/api_gouv_client.py`, `README.md`.

## 3. Conditions pour un découpage sans perte

Ces règles sont une proposition de contrat pour les futures skills.

1. Écrire le périmètre initial et l'unité attendue : comptes SIREN ou établissements SIRET ; présence géographique ou siège ; critères métier.
2. Choisir les subdivisions depuis un référentiel daté. Un découpage géographique initial peut être systématique, conformément à la préférence exprimée, sans requête préalable sur le parent.
3. Conserver tous les critères initiaux dans les enfants. Remplacer seulement le critère parent par ses subdivisions quand leur équivalence est établie.
4. Distinguer couverture et absence de doublons : des zones disjointes peuvent renvoyer la même unité légale. Fusionner les comptes par SIREN sans perdre la trace des segments où ils apparaissent.
5. Ne pas remplacer une population générale par les seules catégories connues. Un découpage par effectif, CA ou catégorie peut perdre les valeurs absentes. Sans moyen de collecter le résidu, qualifier le résultat d'incomplet ou choisir un autre axe.
6. Définir les bornes des intervalles et tester leur sémantique avant de partitionner des montants ; aucune lacune n'est acceptable. Un chevauchement volontaire peut être dédupliqué.
7. Contrôler chaque feuille : total plafonné, pages manquantes, erreurs, doublons de pagination, total changeant. Subdiviser encore ou signaler une couverture non démontrée.
8. Enregistrer pour chaque segment les filtres, le référentiel, les pages lues, les compteurs, les erreurs et l'heure. Le total final est un nombre de SIREN uniques, pas la somme des totaux géographiques.
9. L'exhaustivité reste relative aux données accessibles et à la période de collecte ; l'API ne fournit pas un instantané immuable de toute la base.

Le [code officiel de l'API](https://github.com/annuaire-entreprises-data-gouv-fr/search-api/blob/main/app/elastic/es_search_runner.py#L55-L61) explique le seuil de 10 000 par les problèmes de performance du calcul agrégé. Un total égal à ce seuil ne constitue pas une preuve de couverture.

## 4. Ce qu'il reste à établir avant d'en faire une skill exécutable

| Point | Vérification nécessaire |
|---|---|
| Géographie | Choisir le millésime du COG ; charger toutes les appartenances et exceptions territoriales ; valider Paris, Lyon et Marseille avec les codes réellement retournés par l'API. |
| Filtres combinés | Vérifier si plusieurs contraintes d'établissement sont satisfaites par un même établissement ou éventuellement par des établissements différents ; ne pas présumer l'équivalence parent/enfants. |
| NAF | Fixer la version utilisée par chaque champ. Le CLI embarque la rév. 2 ; ne pas mélanger avec la NAF 2025 ni supposer une conversion un-à-un. |
| Inconnus | Tester les valeurs nulles, absentes ou inconnues et l'existence d'un filtre serveur permettant de les récupérer pour chaque axe candidat. |
| Montants | Vérifier bornes inclusives/exclusives, unité et exercice réellement utilisés par les filtres API ; comparer au contrôle local. |
| Surfaces CLI | Définir comment fournir des filtres structurés et collecter les pages sans NAF obligatoire : aucune commande ne le permet aujourd'hui. |
| Collecte parallèle | `list --segments` utilise séquentiellement le même client et son délai de 0,16 s. Plusieurs clients indépendants ne partagent pas de limiteur : prévoir un débit global et la gestion des réponses 429 avant parallélisation. |
| Inventaire API complet | Étendre la matrice aux autres paramètres (dates, nature juridique, labels, identifiants sectoriels, etc.) après étude de leur portée et de leur capacité à couvrir les inconnus. |

La documentation API fixe actuellement un maximum de 7 requêtes par seconde par IP et demande de respecter `Retry-After` en cas de 429 ; ce plafond n'est pas un débit garanti. La skill décide du plan ; le CLI doit assurer les garanties d'exécution.

## 5. Exemple de plan, pas encore une garantie validée

Demande : comptes ayant un établissement dans le 75, activité NAF rév. 2 `62.02`.

- Résoudre `62.02` en `62.02A` et `62.02B` depuis la référence embarquée.
- Résoudre les arrondissements municipaux de Paris depuis un référentiel, puis valider leur couverture dans la source interrogée.
- Construire les couples arrondissement × sous-classe NAF, en conservant les autres critères éventuels.
- Collecter les pages de chaque couple et affiner les feuilles plafonnées sans écarter les données inconnues.
- Fusionner les SIREN, conserver la provenance des segments, puis produire le CSV et le bilan de couverture.

Ce plan est plus précis que « toujours filtrer davantage » : il rend explicites les relations, les pertes possibles et les preuves qui manquent encore.

## 6. Primitive d'exécution disponible

`list NAF --segments PLAN.json` permet désormais de collecter et fusionner un
plan explicite en une commande. Le CLI valide les champs et l'héritage des
critères, parcourt chaque segment, déduplique les SIREN et conserve la fiche
la plus récente. Une feuille plafonnée fait échouer la commande sans nouvel
export final. La couverture géographique du plan reste à démontrer ; aucune
génération de descendants, collecte parallèle ou reprise n'est intégrée.
Voir `skills/frco-plan-research/references/segment-plans.md` et
`examples/segments-naf-62.02.json` pour le format et un exemple.
