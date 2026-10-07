---
description: Recense les comparaisons de statut de ticket sensibles à la casse (API, SQL, interface)
argument-hint: "[dossier ou fichier à auditer, défaut : src/]"
allowed-tools: Read, Grep, Glob
---

Audite le code d'Argos à la recherche de toute comparaison ou indexation par statut de ticket
qui ne normalise pas la casse au préalable. Ne modifie aucun fichier : produis uniquement un
rapport.

Périmètre : $ARGUMENTS (si vide : tout `src/`, API et interface).

## Démarche

1. Recherche exhaustive, pas seulement le premier cas trouvé : chercher `status` et les valeurs
   `open`, `in_progress`, `closed` sans tenir compte de la casse, puis lire chaque occurrence
   dans son contexte.
2. Formes à examiner :
   - JS : `===`, `!==`, `==`, `switch`/`case`, `includes`, `indexOf`, `filter`, `find` ;
   - indexation par statut : `LABELS[ticket.status]`, `counts[status]`, clés d'objet ;
   - SQL : `WHERE status = ?`, `IN (…)`, `GROUP BY status` sans `LOWER()` (SQLite compare le
     texte en tenant compte de la casse) ;
   - JSX : classe CSS ou libellé choisi en fonction du statut.
3. Pour chaque occurrence, remonter à l'origine de la valeur comparée. Une comparaison n'est
   sûre que si la forme minuscule est garantie pour toutes les sources : import, validation
   de la route, et données déjà présentes en base.

## Rapport

- Un tableau : `fichier:ligne` | extrait | origine de la valeur | verdict (à risque / sûr, avec
  la raison) | correction suggérée.
- Une ligne de bilan : « N comparaison(s) à risque ». S'il n'y en a aucune, écrire exactement :
  « Aucune comparaison de statut à risque. »
