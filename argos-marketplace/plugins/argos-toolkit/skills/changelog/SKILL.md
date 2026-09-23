---
name: changelog
description: Rédige l'entrée de changelog des commits non encore publiés d'Argos, à partir de l'historique Git au format Conventional Commits. À utiliser avant une livraison ou quand on demande « qu'est-ce qui a changé ».
---
Produire une entrée de changelog pour les commits depuis le dernier tag Git (ou depuis le
premier commit s'il n'y a aucun tag) :

1. Lister les commits avec `git log --no-merges --pretty=format:'%h %s' <dernier-tag>..HEAD`.
2. Les regrouper par type Conventional Commits : `feat` → « Nouveautés », `fix` → « Corrections »,
   `docs`, `test`, `refactor`, `chore` → « Maintenance ». Ignorer les commits de fusion.
3. Reformuler chaque ligne pour un lecteur non technique, en français, sans le préfixe de type.
4. Signaler à part tout commit dont le message ne respecte pas le format.

Afficher le résultat en Markdown, sans modifier aucun fichier sauf demande explicite.
