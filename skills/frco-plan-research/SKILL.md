---
name: frco-plan-research
description: Planifier une recherche frco en reliant les champs et leurs granularités, décomposer un périmètre en segments couvrants, préserver les données inconnues et contrôler la couverture. Utiliser pour les collectes multi-zones ou larges, sans supposer des options absentes du CLI.
---

# Décomposer une recherche sans perdre de comptes

Lire [references/field-relations.md](references/field-relations.md) pour choisir les axes et comprendre leurs limites. Cette skill pilote le raisonnement ; elle n'ajoute pas d'API, d'options CLI ou de garantie d'exhaustivité.

## Définir la population

Extraire de la demande la zone, le type de présence (siège ou au moins un établissement), l'activité avec sa nomenclature, les critères métier, les exclusions et l'unité attendue (SIREN ou SIRET). Ne pas inventer de NAF, statut actif ou seuil financier. Demander uniquement les informations réellement nécessaires qui manquent.

Conserver les valeurs inconnues lorsqu'aucun critère demandé ne les exclut. Si le critère exige de vérifier une valeur (par exemple CA supérieur à un seuil), distinguer les entreprises éligibles des valeurs non vérifiables et expliquer le traitement.

## Choisir les segments

Préférence de ce projet : décomposer géographiquement dès le départ, sans sonder d'abord le parent. Résoudre une région en départements et un département en communes avec un référentiel daté. Traiter Paris, Lyon et Marseille via leurs arrondissements municipaux lorsque la couverture et les codes API sont établis. Adapter le niveau initial à la demande plutôt que d'énumérer inutilement des zones hors périmètre.

Une requête sur un département ne devient pas une recherche sur d'autres départements. Ne pas générer les codes postaux ou les codes communaux à partir de simples préfixes. Les codes postaux sont une correspondance, pas un étage universel de la hiérarchie administrative.

Pour chaque segment, conserver les critères initiaux ; remplacer le parent par ses descendants seulement si leur réunion couvre ce parent. Les découpages d'activité doivent inclure tous les descendants de la nomenclature demandée. Les critères indépendants se croisent ; ce ne sont pas des niveaux d'une même hiérarchie.

Pour un total plafonné dans une feuille, affiner encore si une partition couvrante est disponible. Ne pas partitionner arbitrairement par CA, effectif ou catégorie en oubliant les inconnus. Si leur collecte n'est pas possible, changer d'axe ou déclarer la couverture non démontrée. Ne pas affirmer que 10 000 constitue le total exact.

## Vérifier que le plan est exécutable

Dans la version 0.1.0 :

- `list` exige une classe/sous-classe NAF rév. 2 et peut exécuter des segments `--department`, `--region` ou `--city CODE`.
- `list --segments PLAN.json` exécute un plan explicite et fusionne les résultats par SIREN ; voir [references/segment-plans.md](references/segment-plans.md) pour son format et ses garanties.
- Les sections/divisions/groupes NAF doivent être résolus en codes acceptés. Il n'existe pas de mode sans NAF, de manifeste d'exécution exporté ni de parallélisme intégré.

Exécuter les segments compatibles déjà autorisés. Si une primitive manque, produire les segments et la lacune concrète ; ne pas inventer une commande ou créer un script d'appel/collecte ad hoc. Respecter le choix de l'utilisateur d'exprimer la stratégie dans des skills. Toute extension du CLI reste une tâche de code distincte.

## Collecter, fusionner et rendre compte

Une sous-recherche peut nécessiter plusieurs pages. La limite de résultats s'applique au jeu recherché, pas à une seule page. Pour chaque feuille, enregistrer filtres exacts, référentiel/version, heure, total annoncé, pages récupérées, résultat de l'exécution et chemin d'export. Distinguer zéro résultat, échec et résultat plafonné.

Préparer le plan une fois et privilégier un seul `list --segments` pour éviter les relances et les fusions ad hoc. `list` écrit `prospects.json` par défaut ; utiliser `--output` pour choisir le fichier final. Pour des collectes séparées sans plan, donner un chemin distinct à chaque feuille. L'extension `.json` ou `.csv` choisit le format.

La fusion de comptes est une union par SIREN, pas une somme des totaux. Pour des sites, la clé est SIRET, mais `list --segments` collecte uniquement des comptes. Le CLI conserve la fiche entière la plus récente et affiche le nombre d'occurrences et de SIREN uniques. Il n'exporte pas de provenance par SIREN ni de rapport de divergences ; conserver le plan source et ne pas présenter ces détails comme disponibles. Ne pas fusionner les listes d'établissements comme si elles étaient exhaustives.

Pour paralléliser, il faut un limiteur partagé entre tous les appels. Le client actuel attend 0,16 s entre appels d'une même instance ; plusieurs instances peuvent ensemble dépasser le débit. La documentation API annonce au maximum 7 requêtes/s/IP, sans débit garanti, et prescrit `Retry-After` sur 429. Faute d'un mécanisme global fiable, exécuter les segments séquentiellement ; ne pas lancer 20 collectes simultanées.

Restituer les comptes uniques collectés, les segments terminés/plafonnés/en erreur et les inconnus éventuellement exclus. Ne qualifier la couverture de complète que pour le périmètre et les données accessibles, après validation de la partition et du parcours de toutes les feuilles. Des données changeant pendant la collecte ne constituent pas un instantané figé.

Références maintenues : [documentation API](https://recherche-entreprises.api.gouv.fr/docs/), [seuil dans le code officiel](https://github.com/annuaire-entreprises-data-gouv-fr/search-api/blob/main/app/elastic/es_search_runner.py#L55-L61). Si le checkout contient `docs/research-field-map.md`, le lire pour l'état détaillé des vérifications encore nécessaires, sans transformer les hypothèses en garanties.
