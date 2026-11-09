# Exécuter un plan de collecte

Depuis le checkout :

```sh
uv run frco list 62.02 --department 75 --segments plan-paris.json -o comptes-paris.json
```

`plan-paris.json` est un fichier de données préparé par l'agent, pas un script.

```json
{
  "version": 1,
  "segments": [
    {"id": "paris15-a", "city": "75115", "naf": "62.02A"},
    {"id": "paris15-b", "city": "75115", "naf": "62.02B"}
  ]
}
```

Cet exemple couvre les deux sous-classes demandées dans le seul 15e arrondissement. Il n'est pas un plan complet du département. Pour couvrir le 75, résoudre et inclure toutes les subdivisions pertinentes depuis un référentiel officiel ; ne pas annoncer que cet exemple couvre Paris.

## Contrat du plan

- Objet racine contenant uniquement `version: 1` et une liste non vide `segments`.
- Chaque segment contient un `id` unique et éventuellement `naf`, `region`, `department`, `city`. Les valeurs sont des chaînes non vides sans espaces périphériques. Les autres champs sont refusés.
- `city` exige un code INSEE, pas un nom ni un code postal. Les codes doivent provenir d'un référentiel ; le CLI n'en vérifie pas l'appartenance géographique.
- Les critères de la commande sont hérités. Un critère géographique déjà présent ne peut pas être remplacé ; ajouter un niveau plus fin conserve aussi le parent. Le NAF du segment doit être inclus dans celui de la commande.
- Les seuils et le statut ne peuvent pas être redéfinis dans les segments. Ne pas ajouter des filtres de CA ou d'effectif dans la commande si la demande initiale n'en contient pas.
- Le plan et la destination d'export doivent être des chemins distincts. Le format de l'export suit `.json` ou `.csv` ; sans `-o`, `prospects.json`.

## Exécution et erreurs

Tous les segments sont validés avant le réseau. Ils sont ensuite exécutés séquentiellement, avec un client commun qui espace ses appels. Chaque segment récupère toutes ses pages. Le total final peut dépasser 10 000, mais chaque feuille doit rester sous le plafond.

Un segment plafonné ou en erreur provoque l'échec de toute la commande avec son identifiant sur stderr ; aucun nouvel export global n'est écrit, un ancien fichier est conservé. Affiner la feuille en gardant les critères, puis mettre à jour le plan. La reprise automatique et la conservation des feuilles réussies ne sont pas intégrées : une relance recollecte le plan.

Les SIREN présents dans plusieurs segments ne sont exportés qu'une fois, avec la fiche entière la plus récente ; égalité de date : première occurrence conservée. Le bilan stderr indique segments terminés, occurrences avant fusion et SIREN uniques. Le JSON sur stdout est identique au tableau exporté. Aucun rapport par segment ou provenance par SIREN n'est exporté.

Le CLI ne prouve pas que les segments couvrent la population initiale. Conserver le référentiel, les critères et le raisonnement de couverture dans le compte rendu de l'agent ; distinguer « tous les segments fournis ont réussi » et « tout le périmètre est couvert ».

Pour une première illustration sans correspondances géographiques externes, le checkout fournit `examples/segments-naf-62.02.json`, qui couvre les sous-classes A et B de la classe rév. 2 `62.02`. Si une sous-classe plafonne, il faut encore la subdiviser.

Pour résoudre des communes, l'[API Découpage administratif](https://geo.api.gouv.fr/decoupage-administratif/communes) documente `/departements/{code}/communes`. Son service couvre également les arrondissements ; vérifier les types et les codes retournés avant de préparer le plan. Les arrondissements municipaux de Paris/Lyon/Marseille doivent être distingués des arrondissements départementaux.
