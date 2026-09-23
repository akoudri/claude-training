# Lab M3 — Livrer les commentaires sur ticket

## Contexte

Argos est corrigé et configuré depuis les labs M1 et M2. La fonctionnalité suivante touche trois
fronts à la fois : une migration de base de données, un endpoint API, une interface. Ce lab fait
passer d'une session unique à une coordination multi-agents pour la livrer.

## Prérequis

- Argos avec CLAUDE.md, la commande `/audit-statuts` et le hook de protection des migrations en
  place (lab M2).
- Avoir lu la distinction sub-agent / agent team vue en module.
- Aucun sub-agent créé au préalable : c'est la première tâche de ce lab.
- Les agent teams sont expérimentales et désactivées par défaut. Les activer avant de lancer la
  session, dans `.claude/settings.local.json` (non versionné) :
  `{ "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }`, ou par
  `export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- Le dépôt Argos est un dépôt Git avec un état propre (`git status`) : c'est indispensable pour
  les worktrees et pour relire le diff de l'équipe.

## SOCLE — pour tous

1. **Créer un sub-agent de revue**
   Écrire `.claude/agents/reviewer.md` : un rôle unique (relire un diff avant de le proposer),
   un jeu d'outils restreint en lecture seule (`Read, Grep, Glob`).
   - [ ] Le sub-agent apparaît dans `/agents` et peut être invoqué explicitement (`@reviewer`,
     ou « utilise le sub-agent reviewer pour… »).

2. **Décomposer la fonctionnalité**
   Avant de lancer quoi que ce soit, faire écrire par l'agent principal un découpage en trois
   sous-tâches aux périmètres de fichiers disjoints : migration + API, interface, tests.
   - [ ] Le découpage proposé ne fait apparaître aucun fichier partagé entre deux sous-tâches.

3. **Orchestrer l'équipe**
   Demander explicitement une équipe d'agents (« crée une équipe de trois coéquipiers… »), en mode
   superviseur/workers sur ce découpage, et demander d'être alerté en cas de risque de conflit
   avant toute fusion. Les coéquipiers apparaissent sous la zone de saisie : flèches pour en
   choisir un, `Entrée` pour lire sa session ou lui écrire.
   - [ ] Les trois sous-tâches sont exécutées, chacune dans son périmètre annoncé.
   - [ ] Des coéquipiers ont bien été créés (et pas seulement des sub-agents) : sinon, redemander
     explicitement une équipe.

4. **Faire relire par le sub-agent**
   Une fois le travail des trois agents rassemblé, invoquer explicitement le sub-agent de revue
   sur l'ensemble du diff avant de considérer la fonctionnalité terminée.
   - [ ] Le sub-agent produit une relecture identifiant au moins un point d'attention réel
     (convention, test manquant, ou confirmation explicite qu'il n'y en a pas).

5. **Vérifier le résultat**
   Lancer la suite de tests complète et tester manuellement l'ajout d'un commentaire sur un
   ticket.
   - [ ] Les tests passent, y compris ceux ajoutés pour la nouvelle fonctionnalité.
   - [ ] Un commentaire ajouté sur un ticket est bien persisté et visible dans l'interface.

## EXTENSION — pour aller plus loin

- Refaire l'orchestration en isolant chaque agent dans son propre worktree plutôt que dans le même
  répertoire de travail, et comparer la difficulté de suivi par rapport au socle. Soit à la main
  (`git worktree add -b feature/comments ../argos-comments` puis `claude` dans ce dossier), soit
  avec `claude --worktree comments`, qui crée le worktree dans `.claude/worktrees/`.
- Faire tourner la suite de tests dans une seconde session, puis demander depuis la session
  active : « préviens-moi quand la session de tests a fini » (messagerie inter-sessions, Claude
  Code 2.1.236 ou plus récent). `/list-agents` montre les sessions joignables ; nommer la session
  de tests avec `/rename tests` pour la retrouver facilement.
- Demander au sub-agent de revue d'évaluer si le découpage en trois agents était le bon
  dimensionnement pour cette fonctionnalité, ou si un sub-agent unique aurait suffi.

## Pièges & indices

- Un découpage qui laisse un fichier de configuration partagé entre deux agents (par exemple le
  routeur API) est une source de conflit quasi certaine : le signaler et le faire trancher avant
  de lancer l'exécution.
- Fusionner dès qu'un agent semble avoir terminé, sans attendre les autres, est le piège le plus
  fréquent de ce lab : le mode superviseur/workers suppose d'attendre l'ensemble.
- Un sub-agent de revue invoqué avant que tout le travail soit rassemblé ne peut juger que d'une
  partie du diff : l'invoquer une fois l'ensemble consolidé, pas à chaud sur chaque sous-tâche.
  Avec des outils en lecture seule, il ne peut pas lancer `git diff` lui-même : l'agent principal
  doit lui transmettre le diff complet.
- La nouvelle table passe par une **nouvelle** migration (`migrations/003_…sql`) : le hook du
  lab M2 doit la laisser créer. S'il la bloque, c'est le hook qui est trop large.
- Une équipe d'agents consomme nettement plus de tokens qu'une session unique : c'est le prix de
  l'exercice, pas un réflexe à adopter pour toute tâche.
- Si la session est reprise (`/resume`) ou rembobinée (`/rewind`), les coéquipiers ne sont pas
  restaurés : demander au superviseur d'en recréer.
- Si la commande `/audit-statuts` posée en M2 n'est pas relancée sur le nouveau code, une
  régression sur la casse des statuts peut passer inaperçue : c'est l'occasion de vérifier qu'un
  hook ou une commande posée tôt reste utile plus tard.

## Livrable

Un dépôt Argos avec la fonctionnalité de commentaires sur ticket livrée par trois agents
coordonnés, relue par le sub-agent de revue, tests au vert. Ce dépôt sert de point de départ au
lab M4, qui y ajoute les garde-fous de sécurité (permissions, sandboxing, réseau, credentials).
