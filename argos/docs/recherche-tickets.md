# Recherche de tickets par mot-clé

## Décisions de périmètre

| Question | Décision |
|---|---|
| Champs concernés | Titre **et** description : un ticket correspond si le mot-clé apparaît dans l'un ou l'autre. |
| Casse et accents | Insensible aux deux : « echec » trouve « Échec », et inversement. |
| Aucun ticket ne correspond | L'API renvoie `200` et une liste vide (ce n'est pas une erreur) ; l'interface affiche « Aucun ticket ne correspond à « … ». ». |

Règles complémentaires :

- Le mot-clé est cherché comme sous-chaîne : « pann » trouve « Panne ».
- Les espaces en début et en fin sont ignorés ; un mot-clé vide (ou fait d'espaces) équivaut à
  l'absence de recherche.
- La recherche se combine avec le filtre de statut (`open`, `closed`, `all`).
- `%` et `_` sont cherchés littéralement, pas comme jokers SQL.
- Un `q` qui n'est pas un texte (paramètre répété) est refusé : `400`, « Le mot-clé de recherche
  doit être un texte ».

## Conception

- API : paramètre `q` sur `GET /api/tickets` (`/api/tickets?status=open&q=panne`).
- Le filtrage reste en SQL (`repositories/tickets.js`). La normalisation (Unicode NFD, suppression
  des diacritiques, minuscules) est faite par `normalize` (`src/api/text.js`), enregistrée comme
  fonction SQLite par `openDb` : SQLite ne sait ni ignorer les accents ni mettre en minuscules
  hors ASCII.
- Interface : zone « Rechercher » à côté des filtres de statut ; message dédié quand la recherche
  ne trouve rien.

## Plan de tests (ordre du cycle TDD)

1. Une recherche trouve un ticket par son titre.
2. Une recherche trouve un ticket par sa description.
3. Une recherche sans résultat renvoie `200` et `[]`.
4. La recherche est insensible à la casse.
5. La recherche est insensible aux accents, dans les deux sens.
6. La recherche se combine avec le filtre de statut.
7. Un `q` vide ou fait d'espaces renvoie la liste non filtrée.
8. `%` et `_` sont cherchés littéralement.

   Cas ajoutés pendant le cycle TDD (absents du plan initial) :
   - un `q` répété (`?q=a&q=b`), qu'Express transmet sous forme de tableau, est refusé par un
     `400` au lieu de provoquer une erreur 500 ;
   - un mot-clé à cheval sur le titre et la description (« panne imprimante » pour le titre
     « Panne » et la description « imprimante… ») ne correspond pas : la recherche porte sur
     l'un **ou** l'autre champ.
9. Le client API encode `q` dans l'URL.
10. L'interface affiche le message « aucun résultat ».
11. Budget de performance : recherche sur 10 000 tickets (`npm run test:perf`, hors `npm test`).
