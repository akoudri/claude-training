# Lab M2 — Consigner Argos

## Contexte

Le bug de filtrage des statuts est corrigé depuis le lab M1, mais rien n'a encore été consigné :
un nouvel agent qui ouvrirait Argos aujourd'hui redécouvrirait seul les commandes utiles et les
conventions du projet. Ce lab pose les trois briques de personnalisation vues en module : un
fichier de contexte, une commande réutilisable, un garde-fou automatique.

## Prérequis

- Argos avec le correctif du lab M1 appliqué et la suite de tests au vert.
- Claude Code installé et authentifié (lab M1).
- Aucune connaissance préalable des hooks ou des commandes personnalisées : c'est l'objet du lab.

## SOCLE — pour tous

1. **Rédiger le CLAUDE.md d'Argos**
   Créer le fichier à la racine du dépôt avec, au minimum, une section de vue d'ensemble, les
   commandes utiles (test, lint) et la convention de statut en minuscules issue du lab M1.
   - [ ] Le fichier existe, reste court (moins d'une page), et ne contient que des faits
     vérifiables.
   - [ ] Une nouvelle session ouverte sur Argos restitue spontanément ces informations sans
     qu'on les redonne en prompt.

2. **Créer la commande `/audit-statuts`**
   Écrire `.claude/commands/audit-statuts.md` avec une description claire et une consigne :
   repérer toute comparaison de statut qui ne normalise pas la casse au préalable.
   - [ ] La commande apparaît dans la liste des commandes disponibles (taper `/`).
   - [ ] Sa première exécution recense les comparaisons encore sensibles à la casse en dehors du
     filtre corrigé en M1 (il en reste, notamment côté statistiques et interface).
   - [ ] Après correction de ces occurrences, une seconde exécution n'en remonte plus aucune, et
     les compteurs de l'en-tête retombent juste.

3. **Poser un hook de protection**
   Configurer dans `.claude/settings.json` un hook `PreToolUse` (outils `Edit|Write|MultiEdit`)
   qui lance un petit script : celui-ci lit l'appel d'outil en JSON sur son entrée standard et
   refuse, par un code de sortie 2, toute modification d'une migration **existante** de
   `migrations/`. Une migration déjà appliquée est immuable ; en créer une nouvelle doit rester
   possible (le lab M3 en a besoin).
   - [ ] Une tentative de modification d'un fichier de migration existant est refusée, avec un
     message qui explique pourquoi.
   - [ ] La création d'une nouvelle migration et les modifications hors de ce dossier restent
     possibles normalement.

4. **Vérifier l'ensemble**
   Rouvrir une session fraîche sur Argos et confirmer que les trois éléments sont actifs sans
   configuration supplémentaire.
   - [ ] CLAUDE.md, la commande et le hook sont tous les trois opérationnels dès l'ouverture.

## EXTENSION — pour aller plus loin

- Installer le plugin `argos-toolkit` depuis la marketplace de démonstration fournie par l'équipe
  pédagogique (`/plugin marketplace add ../argos-marketplace` puis
  `/plugin install argos-toolkit@janus-argos`) et observer ce qu'il ajoute à la session : une
  skill `/argos-toolkit:changelog`, un sub-agent `test-runner`, un hook `SessionStart`.
- Réécrire `/audit-statuts` sous forme de skill (`.claude/skills/audit-statuts/SKILL.md`), le
  format désormais recommandé : comparer avec la commande (invocation, chargement automatique
  par Claude quand la description correspond).
- Comparer, avec l'agent, ce que le plugin installé aurait permis d'obtenir plus rapidement que la
  commande et le hook écrits à la main dans le socle.
- Écrire une seconde commande qui automatise une autre tâche répétée identifiée sur Argos depuis
  le début de la formation.

## Pièges & indices

- Un CLAUDE.md qui reprend l'intégralité du README du projet perd son intérêt : il doit rester
  plus court et plus factuel qu'une documentation.
- Un hook de protection trop large (par exemple sur tout le dossier `src/`, ou sur la simple
  création de fichiers dans `migrations/`) empêche aussi les évolutions légitimes : commencer
  étroit, élargir seulement si nécessaire.
- Un hook ne se déclare pas par une règle `"action": "deny"` : c'est une commande exécutée par
  Claude Code, qui bloque l'outil en sortant avec le code 2 (ou en renvoyant un
  `permissionDecision: "deny"` en JSON). Le script peut s'appuyer sur `$CLAUDE_PROJECT_DIR`.
- Tester le hook hors session en lui envoyant un JSON à la main, par exemple :
  `echo '{"tool_input":{"file_path":"migrations/001_create_tickets.sql"}}' | node .claude/hooks/<script>`
  puis `echo $?`.
- Pour une simple interdiction sans exception, une règle de permission suffit
  (`"permissions": {"deny": ["Edit(/migrations/**)"]}`) ; le hook se justifie ici parce qu'il
  distingue migration existante et nouvelle migration.
- Si la commande `/audit-statuts` ne remonte rien alors qu'une occurrence existe, vérifier que la
  consigne demande bien une recherche exhaustive et pas seulement un cas particulier.
- Une commande qui fonctionne à la première tentative sans avoir été relue mérite d'être testée
  une seconde fois sur un cas volontairement piégeux avant d'être considérée fiable.

## Livrable

Un dépôt Argos avec CLAUDE.md, la commande `/audit-statuts` et le hook de protection des
migrations, tous trois vérifiés sur une session fraîche. Ce dépôt configuré sert de point de
départ au lab M3, qui y ajoute la coordination multi-agents sur une fonctionnalité réelle.
