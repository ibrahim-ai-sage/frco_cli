# Relations à utiliser pour construire un plan frco

Référence de travail au 29 octobre 2026. Les relations conceptuelles ci-dessous ne prouvent pas à elles seules que l'API couvre tous les descendants d'un segment.

| Axe | Relations | Règle de couverture |
|---|---|---|
| Identité | Une unité légale SIREN possède plusieurs établissements SIRET ; le siège est un établissement particulier. | Dédupliquer selon l'unité demandée. Ne pas confondre présence par établissement et siège. |
| Géographie administrative | Région → département → commune ; arrondissements municipaux dans Paris/Lyon/Marseille. | Utiliser les appartenances officielles datées, traiter les exceptions territoriales et vérifier les codes réellement acceptés. |
| Géographie postale | Commune ↔ code postal, plusieurs-à-plusieurs. | Consulter une table de correspondance ; ne pas substituer les codes postaux à une partition administrative sans démontrer la couverture. |
| Intercommunalité | EPCI → communes membres, branche de zonage distincte. | Ne pas insérer automatiquement l'EPCI dans région → département → commune. Vérifier la fiabilité du filtre API avant d'en faire un axe de collecte. |
| Activité | Section → division → groupe → classe → sous-classe NAF. | Choisir une version, développer tous les enfants officiels ; ne pas mélanger rév. 2 et NAF 2025. |
| Effectif | Tranche codifiée et année de référence. | Ce n'est pas un entier exact. Les valeurs inconnues/non renseignées doivent rester couvertes si la demande ne les exclut pas. |
| Catégorie | PME, ETI, GE, éventuellement absent. | Dimension distincte de l'effectif et du CA ; une catégorie n'est pas déduite d'un seul seuil. |
| Finances | Historique par exercice ; dernier CA disponible ; croissance dérivée. | L'absence de CA n'est pas zéro. Pas de découpage financier couvrant sans traitement du résidu inconnu et des bornes. |
| Statut | État de l'unité légale distinct de l'état de chaque établissement. | Ne pas assimiler entreprise active à tous établissements actifs. |
| Sites | Total des établissements distinct du nombre d'actifs. | Multi-site local = plus d'un établissement actif ; ne pas confondre avec le nombre d'adresses. |
| Représentants | Plusieurs acteurs et rôles par unité légale. | Un commissaire aux comptes n'est pas automatiquement un dirigeant ; aucun axe exhaustif par nom de personne n'est établi. |
| Sortie et pagination | Champs projetés, pages et taille de page. | Retirer des champs ne réduit pas la population ; parcourir des pages ne subdivise pas le marché. |

## Correspondances avec le CLI 0.1.0

`list --region` → `region`, `--department` → `departement`, `--city CODE` → `code_commune`, argument NAF → `activite_principale`, effectif → codes de `tranche_effectif_salarie`, CA → `ca_min/ca_max`, `--active-only` → `etat_administratif=A`.

`--city NOM` est différent : le CLI envoie le nom dans `q`, puis contrôle les communes visibles dans le siège et les établissements retournés. Ce mode peut omettre des comptes ; résoudre d'abord le nom en code pour une collecte.

`--multi-site-only` et `--establishments-min/max` sont des filtres locaux après collecte. Ils ne permettent pas de réduire un ensemble plafonné côté serveur.

## Points à vérifier avant de promettre une couverture

- Référentiel géographique/version : communes nouvelles, codes anciens, cas particuliers et arrondissements municipaux. Utiliser la géographie cohérente avec les données recherchées.
- Conjonction des filtres d'établissement : vérifier si le même établissement doit satisfaire toutes les contraintes ou si plusieurs sites d'une unité légale peuvent les satisfaire séparément. Ne pas supposer qu'une transformation de filtre conserve la sémantique.
- Pour chaque axe, inventorier les valeurs absentes, inconnues et hors nomenclature. Le fait qu'une nomenclature ait des catégories finies ne prouve pas que tous les résultats ont une catégorie.
- Pour le CA, vérifier les bornes et l'exercice du filtre serveur avant tout découpage par intervalles. Le contrôle local du CLI repose sur le dernier CA publié.
- Ne pas utiliser un SIREN/SIRET dans `q` avec des filtres comme preuve d'appartenance : l'API ignore ces filtres en recherche directe.
- Une feuille plafonnée ou un segment en erreur empêche de conclure à la couverture complète. Ne pas remplacer les résultats manquants par une estimation silencieuse.

## Sources

- [Géographie administrative et appartenances, Insee](https://www.insee.fr/fr/information/8064273).
- [Différence code commune/code postal, Insee](https://www.insee.fr/fr/information/1302169?question=quel-est-le-code-insee-de-ma-commune).
- [Correspondances postales officielles, La Poste](https://www.data.gouv.fr/datasets/base-officielle-des-codes-postaux).
- [Structure NAF rév. 2, Insee](https://www.insee.fr/fr/information/3281579).
- [Établissement, Insee](https://www.insee.fr/fr/metadonnees/definition/c1377) et [entreprise statistique, Insee](https://www.insee.fr/fr/metadonnees/definition/c1496).
- [Documentation API Recherche d'entreprises](https://recherche-entreprises.api.gouv.fr/docs/).

Les comportements CLI sont vérifiables dans `src/frco/cli`, `src/frco/services/prospect_list_service.py`, `src/frco/services/activity_reference.py` et `src/frco/clients/api_gouv_client.py` du checkout. Cette référence est portable avec la skill ; la cartographie détaillée du projet reste dans `docs/research-field-map.md` si elle est disponible.
