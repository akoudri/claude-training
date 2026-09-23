# Lab M6 — Construire la recherche

## Contexte

Argos est corrigé, configuré, coordonné en multi-agents, sécurisé et reproductible depuis les
labs précédents. Ce dernier lab construit la recherche de tickets par mot-clé, non pas en
improvisant, mais selon le cycle vu en module : brainstorm, plan, TDD, revue.

## Prérequis

- Argos avec l'environnement reproductible du lab M5 en place.
- Le sub-agent `reviewer` créé au lab M3, toujours disponible.
- Superpowers installé (`/plugin install superpowers@claude-plugins-official`, depuis la
  marketplace officielle déjà connue de Claude Code), ou à défaut le cycle mené manuellement en
  suivant la même discipline. Ses skills s'invoquent par exemple avec
  `/superpowers:brainstorming`.

## SOCLE — pour tous

1. **Brainstorm**
   Avant toute ligne de code, faire clarifier par l'agent le périmètre exact de la recherche :
   champs concernés (titre, description, ou les deux), sensibilité à la casse et aux accents,
   comportement attendu si aucun ticket ne correspond.
   - [ ] Ces trois points sont explicitement tranchés et notés dans un fichier versionné (par
     exemple `docs/recherche-tickets.md`) avant de passer au plan.

2. **Plan**
   Faire décomposer la fonctionnalité en une liste de cas de test à écrire, dans l'ordre où ils
   seront traités.
   - [ ] Le plan couvre au moins : une recherche qui trouve un résultat, une recherche sans
     résultat, une recherche insensible à la casse.

3. **TDD — premier cas**
   Écrire le test du premier cas (rouge), le voir échouer, écrire le minimum de code pour le
   faire passer (vert), puis refactorer si nécessaire.
   - [ ] Le test échoue avant toute implémentation.
   - [ ] Le test passe après l'implémentation minimale.

4. **TDD — cas suivants**
   Répéter le cycle rouge/vert/refactor pour chacun des cas restants du plan.
   - [ ] Chaque cas du plan a son test, écrit avant son implémentation.
   - [ ] L'ensemble des tests de la fonctionnalité passe.

5. **Revue**
   Invoquer explicitement le sub-agent `reviewer` sur l'ensemble du diff de la fonctionnalité.
   - [ ] La revue confirme l'absence de régression et la cohérence avec les conventions d'Argos,
     ou identifie un point à corriger avant de considérer le lab terminé.

6. **Vérification finale**
   Lancer la suite de tests complète d'Argos.
   - [ ] Aucune régression sur les fonctionnalités des modules précédents.

## EXTENSION — pour aller plus loin

- Faire tourner une sous-tâche simple de cette fonctionnalité (par exemple, un seul cas de test)
  sur un modèle local plutôt que sur Claude, et comparer le résultat et le temps de réponse.
  Avec Ollama, qui expose une API compatible Anthropic : `ollama launch claude`, ou
  `ANTHROPIC_BASE_URL=http://localhost:11434 ANTHROPIC_AUTH_TOKEN=ollama claude --model <modèle>`
  avec un modèle capable d'appeler des outils. Le lancer dans une copie du dépôt : le modèle local
  n'offre pas les mêmes garanties.
- Explorer BMAD-METHOD sur un cas fictif court, en observant comment les rôles fixes (Analyst,
  PM, Architect, Dev, QA) redécoupent une demande que l'on vient de traiter soi-même en agent
  team libre.
- Faire évaluer par l'agent si un des cas de test du plan initial manquait une situation limite
  qui n'apparaît qu'une fois la fonctionnalité terminée.

## Pièges & indices

- Écrire l'implémentation avant le test annule l'intérêt du cycle : si un test est vert dès son
  écriture, c'est le signe qu'il a été écrit après le code, pas avant.
- Un refactor qui modifie un résultat de test, même légèrement, n'est pas un refactor : c'est un
  changement de comportement déguisé.
- Une revue demandée avant que tous les cas du plan soient traités ne porte que sur un travail
  partiel : attendre la fin du cycle TDD complet.
- Les accents : « Échec » et « echec » ne sont égaux ni en JavaScript ni en SQLite sans
  normalisation explicite (Unicode NFD, puis suppression des diacritiques). C'est un bon cas de
  test rouge.
- Sauter le brainstorming parce que la fonctionnalité « semble simple » est le piège le plus
  fréquent : une recherche de tickets soulève plus de décisions implicites qu'il n'y paraît.

## Livrable

Un dépôt Argos avec la recherche de tickets livrée selon un cycle brainstorm → plan → TDD →
revue complet, tests au vert, relue par le sub-agent. C'est l'état final du fil rouge de la
formation : Argos, corrigé, configuré, coordonné, sécurisé, reproductible et construit avec
discipline.
