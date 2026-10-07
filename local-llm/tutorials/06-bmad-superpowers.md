# Combiner BMAD et superpowers dans Claude Code

Ce tutoriel montre comment faire travailler ensemble deux surcouches de Claude Code qui se recouvrent en partie :

- **BMAD Method** : une méthode de développement agile pilotée par l'IA. Elle produit les documents de planification (spec, architecture, PRD) et découpe le travail en stories ordonnées.
- **superpowers** : une bibliothèque de skills de discipline d'ingénierie. Elle couvre les plans d'implémentation, le TDD, le travail par sous-agents, la revue de code et la vérification avant de déclarer une tâche finie.

Les deux savent planifier, coder et relire. Utilisés tels quels, ils lancent deux boucles « plan → code → revue » concurrentes. Ce tutoriel fixe une frontière nette entre les deux et la vérifie sur un exercice exécuté de bout en bout.

> **Règle de partage** : BMAD décide **quoi** construire et **dans quel ordre**. superpowers décide **comment** construire chaque story.

- **Versions testées** :
  - BMAD Method 6.13.0-next : c'est la branche `main` du dépôt, celle que `skills add` installe ; la release npm est 6.12.1 ;
  - superpowers 6.4.1 ;
  - Claude Code 2.1.291.
- **Modèles** : Claude via l'API Anthropic. L'orchestrateur tournait sur Opus 5.5. Les sous-agents de superpowers ont pris Haiku 4.5 pour implémenter et Sonnet 5.5 pour relire. La section 7 indique ce qui tient sur le LLM local `ornith-code`.
- **Ce qui a été exécuté** : l'installation, `bmad setup`, la spec, le découpage en 5 stories, puis la construction complète de la story 1.1 par superpowers, avec le suivi du ticket jusqu'à `done`. Les mesures sont en section 6.
- **Ce qui n'a pas été exécuté** : les stories 1.2 à 1.5 et `bmad-retrospective`. Ils suivent le même schéma, mais n'ont pas été mesurés.

Sources officielles :

| Sujet | URL |
|---|---|
| Dépôt BMAD Method (installation) | https://github.com/bmad-code-org/BMAD-METHOD |
| Choisir un parcours de planification | https://docs.bmad-method.org/plan/choose-a-planning-path/ |
| `bmad-build` et les skills d'implémentation | https://docs.bmad-method.org/build/build-a-change/ |
| superpowers | https://github.com/obra/superpowers |

---

## 1. Qui fait quoi

### 1.1 Ce que chaque outil apporte

| Besoin | BMAD | superpowers |
|---|---|---|
| Faire émerger une idée floue | `bmad-forge-idea`, `bmad-brainstorming` | `brainstorming` |
| Écrire le contrat (exigences, hors périmètre) | `bmad-spec`, `bmad-prd` | (spec dans `brainstorming`) |
| Décisions techniques partagées par plusieurs epics | `bmad-architecture` | — |
| Découper en stories ordonnées, suivre leur état | `bmad-ticket` | — |
| Plan d'implémentation tâche par tâche | (dans `bmad-build`) | `writing-plans` |
| Isoler le travail sur une branche | — | `using-git-worktrees` |
| Coder en TDD, une tâche par sous-agent | (dans `bmad-build`) | `test-driven-development`, `subagent-driven-development` |
| Revue de code | `bmad-code-review` | `requesting-code-review` |
| Vérifier avant de dire « fini », merger | — | `verification-before-completion`, `finishing-a-development-branch` |
| Rétrospective d'epic | `bmad-retrospective` | — |

BMAD est fort en amont : contrat, découpage, état des tickets, rétrospective. superpowers est fort en aval : TDD strict, revues par des sous-agents indépendants, vérification et intégration Git. Le recouvrement se situe au milieu, autour de `bmad-build`.

### 1.2 Le flux retenu

```
          BMAD (planification)                         superpowers (une story)
┌──────────────────────────────────────┐   ┌──────────────────────────────────────────┐
│ intention                            │   │ writing-plans  (exigences = spec+entrée) │
│   └─ bmad-forge-idea   (optionnel)   │   │ using-git-worktrees                      │
│   └─ bmad-spec        → spec-*.md    │──►│ subagent-driven-development (TDD)        │
│   └─ bmad-architecture (si besoin)   │   │ requesting-code-review                   │
│   └─ bmad-ticket      → tickets.toml │   │ verification-before-completion           │
└──────────────────────────────────────┘   │ finishing-a-development-branch           │
          ▲                                └──────────────────────────────────────────┘
          │   tickets.py mark … in-progress / built        │
          └────────────────────────────────────────────────┘
      `done` (humain), puis bmad-retrospective en fin d'epic
```

On **n'installe pas** `bmad-build`, `bmad-build-auto`, `bmad-code-review` ni `bmad-brainstorming`. Leur rôle est déjà tenu par superpowers, et leur seule présence crée des conflits (section 3).

---

## 2. Installation

### 2.1 Prérequis

Ce tutoriel ne dépend pas de la stack `local-llm` : il utilise Claude avec un compte Anthropic.

| Élément | Installation et vérification |
|---|---|
| Claude Code, connecté à un compte Anthropic (abonnement ou clé d'API) | `claude --version`. L'exercice consomme des tokens : environ 5 $ en API pour les deux phases mesurées (section 6). |
| superpowers | Dans Claude Code : `/plugin install superpowers@claude-plugins-official`, puis redémarrer la session. `/plugin` doit le lister. |
| Node.js + npm (pour `npx skills`) | `node -v` |
| `uv` (scripts Python de BMAD) | `curl -LsSf https://astral.sh/uv/install.sh \| sh`, puis `uv --version`. **Obligatoire** : sans `uv`, `bmad setup` s'arrête. |
| Git | le dépôt du projet doit être initialisé (`git init`) |

### 2.2 Installer BMAD de façon sélective

BMAD se distribue désormais en **skills**. Les anciens agents « PM / Scrum Master / Dev » appelés par des commandes slash n'existent plus sous cette forme. Il y a deux voies d'installation :

- le marketplace Claude Code `bmad-code-org/bmad-plugins`, qui installe des modules entiers ;
- le CLI `skills`, qui permet de **choisir skill par skill**. C'est celle qu'on retient ici.

Pour voir la liste complète des skills (33 au moment du test) :

```bash
npx skills add bmad-code-org/BMAD-METHOD --list
```

Pour installer les skills de planification et de suivi, au niveau du projet et pour Claude Code seulement :

```bash
npx skills add bmad-code-org/BMAD-METHOD -a claude-code -y --copy \
  -s bmad -s bmod-core-tools -s bmod-method \
  -s bmad-spec -s bmad-ticket -s bmad-architecture -s bmad-prd \
  -s bmad-forge-idea -s bmad-retrospective
```

Le rôle de chaque option :

| Option | Effet |
|---|---|
| `-a claude-code` | installe dans `.claude/skills/` du projet, et pas pour les autres agents détectés |
| `-y` | pas de question |
| `--copy` | copie les fichiers au lieu de faire un lien symbolique vers un cache |
| `bmad`, `bmod-core-tools`, `bmod-method` | le hub d'aide et de setup, et les « fiches module » obligatoires (ce ne sont pas des skills à invoquer) |

Ensuite, ouvrez Claude Code dans le projet et demandez :

```
Lance bmad setup.
```

Le skill `bmad` exécute son script de setup avec `uv`. Ce script crée :

- `_bmad/config.toml`, qui contient entre autres le dossier de sortie `_bmad-output` ;
- `_bmad/scripts/` et `_bmad/method/scripts/tickets.py` ;
- `_bmad/custom/`, dont le `.gitignore` exclut `*.user.toml`.

Il crée aussi `skills-lock.json` à la racine. Committez ce fichier : il fige les sources et les empreintes des skills installés.

Sur l'installation testée, `bmad status` répond `current: true` et ne signale aucun problème. Les skills qu'on n'a pas installés apparaissent comme `absent_skills`, ce que la doc du skill décrit comme « optionnel, pas une faute ».

> **Versions** : `skills add` sans référence installe la branche `main`, en version `-next`. Pour une équipe, figez la version avec `skills-lock.json` commité et mettez à jour volontairement avec `bmad setup`, qui exécute `npx skills update`.

### 2.3 Les règles de cohabitation dans `CLAUDE.md`

Les deux bibliothèques s'appuient sur la même règle de priorité : les instructions de l'utilisateur, dont le `CLAUDE.md` du projet, passent avant les skills. C'est donc dans le `CLAUDE.md` qu'on fixe la frontière. Voici la version validée par l'exercice :

```markdown
## BMAD + superpowers : qui fait quoi

- **Planifier (quoi, dans quel ordre)** : skills BMAD — `bmad-forge-idea`, `bmad-prd`,
  `bmad-spec`, `bmad-architecture`, `bmad-ticket`. Leurs documents vont dans `_bmad-output/`.
- **Construire une story (comment)** : skills superpowers. `bmad-build` n'est pas installé
  dans ce projet ; ne pas le réclamer.
- Une entrée de `tickets.toml` issue d'une spec BMAD **est un design approuvé** :
  ne pas relancer `superpowers:brainstorming`. Passer directement à
  `superpowers:writing-plans`, en citant la spec et l'entrée du ticket comme exigences.
- Une story = une branche (`superpowers:using-git-worktrees`), en TDD
  (`superpowers:test-driven-development`), revue (`superpowers:requesting-code-review`)
  et vérifiée (`superpowers:verification-before-completion`) avant d'être déclarée finie.
- Suivi du ticket (BMAD ne le fait pas sans `bmad-build`). Toujours passer le dossier
  de l'initiative : l'initiative active n'existe pas dans un worktree.
  - au démarrage : `uv run _bmad/method/scripts/tickets.py --project-root . mark <initiative> <ref> in-progress`
  - story mergée, tests verts : `... mark <initiative> <ref> built`
  - `done` : seulement quand l'humain le dit (via `bmad-ticket`).
```

Ajoutez aussi au `.gitignore` les dossiers de worktrees : `.worktrees/` (convention superpowers) et `.claude/worktrees/` (outil de worktree intégré à Claude Code, que superpowers a utilisé pendant le test).

---

## 3. Les conflits, et comment ils sont réglés

| Conflit | Symptôme sans règle | Réglage |
|---|---|---|
| **`bmad-build` revendique les stories.** Sa description dit qu'il se déclenche « quand l'utilisateur délègue une fonctionnalité, une story, un bug ». | Demander « construis la story 1.1 » lance `bmad-build`, avec son propre plan, son implémentation et ses relecteurs. La boucle superpowers n'est jamais utilisée. | Ne pas installer `bmad-build` ni `bmad-build-auto`. Le `CLAUDE.md` le rappelle. |
| **Deux « brainstorming ».** `bmad-brainstorming` et `superpowers:brainstorming` répondent tous deux à « aide-moi à réfléchir ». | Selon le modèle, on obtient tantôt l'un, tantôt l'autre. | On n'en garde qu'un en amont : `bmad-forge-idea`, qui produit un brief que `bmad-spec` sait lire. On n'installe pas `bmad-brainstorming`. |
| **superpowers réclame un design approuvé.** Son skill d'amorçage impose `brainstorming` avant toute implémentation. | L'agent refait une phase de questions et une spec dans `docs/superpowers/specs/`, en doublon de la spec BMAD. | La règle « une entrée de `tickets.toml` est un design approuvé ». Pendant le test, `brainstorming` n'a **pas** été invoqué et le plan cite la spec BMAD. |
| **Deux revues de code.** `bmad-code-review` et `superpowers:requesting-code-review`. | Double revue, avec des constats contradictoires. | Seule la revue superpowers est installée. |
| **Statut des tickets.** Dans BMAD, c'est `bmad-build` qui écrit `in-progress`, `in-review` et `built`. | Sans `bmad-build`, les stories restent en `planned` et `tickets.py next` ne propose jamais la suivante. | `tickets.py mark` (règle du `CLAUDE.md`). La commande crée un plan BMAD minimal (frontmatter seul) quand il n'y en a pas. |
| **Deux plans par story.** | Le plan BMAD (`story-<slug>-plan.md` à côté de `tickets.toml`) ne porte que le statut. Le vrai plan est celui de superpowers (`docs/superpowers/plans/AAAA-MM-JJ-<slug>.md`). | C'est voulu : BMAD suit l'état, superpowers garde le détail. Le plan superpowers cite le chemin de la spec et l'entrée du ticket. |

---

## 4. Exercice : de l'intention à la première story livrée

L'exercice porte sur un projet fictif, `acme-salles` : une bibliothèque Node.js de réservation des salles de réunion, sans dépendance et testée avec `node --test`.

### 4.1 Préparer le dépôt

```bash
mkdir acme-salles && cd acme-salles && git init
cat > package.json <<'EOF'
{ "name": "acme-salles", "version": "0.1.0", "private": true,
  "scripts": { "test": "node --test" } }
EOF
printf 'node_modules/\n.worktrees/\n.claude/worktrees/\n' > .gitignore
```

Ensuite, toujours dans le dossier `acme-salles` :
1. installez BMAD avec la commande `npx skills add` de la section 2.2 ;
2. créez le fichier `CLAUDE.md` avec le bloc de la section 2.3 ;
3. ouvrez Claude Code (`claude`) et demandez « Lance bmad setup » ;
4. committez : `git add -A && git commit -m "chore: install BMAD"`.

### 4.2 Planifier avec BMAD

Ouvrez **une nouvelle session** Claude Code et tapez :

```
Utilise bmad-spec puis bmad-ticket.

Intention : la bibliothèque acme-salles doit permettre de réserver des salles de réunion.
- Une réservation = salle (identifiant texte), début, fin (Date), organisateur.
- Refuser une réservation qui chevauche une autre dans la même salle
  (fin exclusive : 10h-11h et 11h-12h ne se chevauchent pas).
- Refuser début >= fin et les durées supérieures à 4 heures.
- Annuler une réservation par son identifiant.
- Lister les créneaux libres d'une salle sur une journée, entre 8h et 19h.
- Stockage en mémoire uniquement. Hors périmètre : persistance, fuseaux horaires,
  récurrence, droits.

Découpe en stories dans l'ordre de construction (repo store). Ne code rien.
```

En session interactive, `bmad-spec` vous pose ses questions sur les zones floues. Par exemple : une durée de 4 h pile est-elle acceptée ? les créneaux sont-ils en heure locale ? Répondez-y : chaque réponse non donnée devient une hypothèse dans la spec.

Le résultat se trouve dans `_bmad-output/` :

```
_bmad-output/initiative-acme-salles/
├── initiative-acme-salles.md
├── tickets.toml                                 # l'initiative et son epic
├── spec-reservation-salles/
│   ├── spec-reservation-salles.md               # 5 capacités CAP-1…CAP-5, hypothèses
│   └── .memlog.md                               # journal des décisions
└── epic-reservation-salles/
    ├── epic-reservation-salles.md
    └── tickets.toml                             # 5 stories, dans l'ordre de construction
```

Le découpage obtenu pendant le test est donné ci-dessous. **Le vôtre sera différent** : un LLM ne produit pas deux fois la même spec. Les noms de dossiers (`initiative-acme-salles`, `epic-reservation-salles`), le nombre de stories et leurs références peuvent changer. Lisez les vôtres dans `_bmad-output/` et dans la sortie de `tickets.py next`, et remplacez-les dans les commandes qui suivent.

| Ref | Story | Couvre | Après |
|---|---|---|---|
| 1.1 | Réserver une salle | CAP-1 | — |
| 1.2 | Lister les créneaux libres | CAP-5 | 1.1 |
| 1.3 | Refuser intervalles invalides et chevauchements | CAP-2, CAP-3 | 1.2 |
| 1.4 | Annuler une réservation | CAP-4 | 1.3 |
| 1.5 | Refactor sweep | — | 1.1–1.4 |

Chaque entrée contient un champ `verify` : ce sont les critères d'acceptation exacts que superpowers transformera en tests. **Relisez le découpage et committez-le.** C'est le point de contrôle humain entre les deux mondes : `bmad-ticket` ne committe pas sans votre accord.

```bash
uv run _bmad/method/scripts/tickets.py --project-root . next     # 1.1 est « ready_to_start »
git add -A && git commit -m "docs(plan): spec and stories for room booking"
```

### 4.3 Construire la story 1.1 avec superpowers

Ouvrez une **nouvelle session**, pour ne pas mélanger le contexte de la planification avec celui de la construction, et tapez :

```
Construis la story 1.1 du ticket BMAD (epic-reservation-salles) en suivant CLAUDE.md.
```

Voici l'enchaînement observé pendant le test, d'après le journal de la session :

1. `tickets.py mark initiative-acme-salles 1.1 in-progress`
2. `superpowers:writing-plans` produit `docs/superpowers/plans/2026-10-06-reserver-une-salle.md`. L'en-tête du plan cite la spec, l'entrée 1 **mot pour mot**, et précise : « L'entrée du ticket est un design approuvé : pas de brainstorming ».
3. `superpowers:using-git-worktrees` crée une branche dédiée.
4. `superpowers:subagent-driven-development` traite 2 tâches. Pour chacune, un sous-agent implémente en TDD (test rouge, puis vert), puis un autre sous-agent relit la conformité au plan et la qualité.
5. `superpowers:requesting-code-review` fait une revue finale de toute la branche. Verdict : « prêt à merger », sans constat critique ni important.
6. `superpowers:verification-before-completion` relance `npm test` : 23 tests passent.
7. `superpowers:finishing-a-development-branch` merge en local dans `main`.
8. `tickets.py mark initiative-acme-salles 1.1 built`

En session interactive, superpowers vous demande de choisir :
- le mode d'exécution du plan : sous-agents, ou exécution en ligne ;
- l'issue de la branche : merge local, PR, ou garder la branche.

Historique obtenu :

```
* 74457a8 chore(tickets): mark story 1.1 built
*   22445c8 Merge branch 'worktree-story-1.1-reserver-salle'
|\
| * 90a2094 feat(booking): reject invalid booking input and copy provided dates
| * a0f87dd feat(booking): reserve a room through the acme-salles entry point
| * d0c5730 docs(plan): implementation plan for story 1.1 and mark it in-progress
|/
* e269f75 docs(plan): spec and stories for room booking
```

### 4.4 Clôturer et passer à la suivante

Relisez le diff. Si la story vous convient, dites à Claude « la story 1.1 est terminée ». `bmad-ticket` la marque alors `done`. Vous pouvez aussi le faire directement :

```bash
uv run _bmad/method/scripts/tickets.py --project-root . mark initiative-acme-salles 1.1 done
uv run _bmad/method/scripts/tickets.py --project-root . next
# "ready_to_start": 1.2   —   "blocked": 1.3, 1.4, 1.5
```

Ensuite, il suffit de recommencer la section 4.3 pour chaque story. Quand toutes les stories de l'epic sont `done`, lancez `bmad-retrospective` sur le dossier de l'epic. Elle juge le résultat d'ensemble au regard des conditions de fin de l'epic : c'est le seul contrôle qui voit les stories ensemble.

---

## 5. Quand ne pas tout dérouler

| Taille du travail | Parcours |
|---|---|
| Faute de frappe, réglage, renommage | Ni BMAD ni superpowers : demandez directement la modification et relisez-la. |
| Une modification claire, en une session | superpowers seul : `brainstorming`, puis `writing-plans`, puis l'exécution. BMAD n'apporte rien ici. |
| Une fonctionnalité en plusieurs sessions (un epic) | `bmad-spec`, puis `bmad-ticket`, puis superpowers pour chaque story. C'est le parcours de ce tutoriel. |
| Un produit en plusieurs epics | Ajoutez `bmad-prd` et `bmad-architecture` avant les specs d'epic, et une rétrospective par epic. |

BMAD se rentabilise quand le travail dépasse une session : la spec et `tickets.toml` gardent le contexte d'une session à l'autre, alors que l'historique de conversation se perd.

---

## 6. Mesures

Les deux phases ont été mesurées sur le projet de l'exercice, avec Claude Code en mode non interactif (`claude -p`, sortie JSON) : les durées, nombres de tours et coûts viennent du rapport de la session. Comme Claude ne pouvait pas poser de questions, le prompt imposait des choix par défaut, que l'agent a notés comme hypothèses dans la spec.

| Phase | Durée | Tours | Coût API | Résultat |
|---|---|---|---|---|
| Planification : `bmad-spec` puis `bmad-ticket` | 5 min 40 s | 17 | 1,47 $ | spec de 4 ko, 5 stories ; découpage relu par un agent indépendant (6 suggestions, toutes appliquées) |
| Story 1.1 : superpowers, du plan au merge | 9 min 13 s | 59 | 3,32 $ | 3 commits et un merge, 23 tests sur 23, ticket en `built` |

Les sous-agents de `subagent-driven-development` ont choisi leur modèle selon le rôle : Haiku pour implémenter, Sonnet pour relire chaque tâche, Opus pour la revue finale. Il y a eu 5 sous-agents au total : 2 pour implémenter, 2 pour relire chaque tâche, 1 pour la revue finale. Cela explique qu'une story ne coûte qu'environ deux fois une planification.

---

## 7. Et avec le LLM local (`ornith-code`) ?

Le [tutoriel Claude Code + LLM local](04-claude-code-vscode-local.md) branche Claude Code sur `ornith-code` : un modèle 9B, avec 64k de contexte, servi par l'Ollama local. La combinaison BMAD + superpowers y est **déconseillée de bout en bout**, et seule une partie est réaliste :

| Étape | Sur `ornith-code` | Pourquoi |
|---|---|---|
| `bmad-spec`, `bmad-ticket`, `bmad-architecture` | Non | Ces skills font de longs dialogues, lisent plusieurs fichiers de référence et lancent un relecteur indépendant. Il faut un modèle capable de raisonner sur l'ensemble. |
| `subagent-driven-development` | Non | Chaque tâche lance au moins 2 sous-agents. Sur un Ollama local qui traite une requête à la fois (`OLLAMA_NUM_PARALLEL=1`), c'est très lent. Et l'exercice du tutoriel 04, beaucoup plus simple, prenait déjà 6 à 7 min sur l'hôte de la configuration de référence. |
| Une story déjà découpée, avec un plan superpowers déjà écrit, exécutée **en ligne** (`superpowers:executing-plans`) en TDD | Possible | Le plan et l'entrée du ticket donnent un contexte court et précis. C'est le cas où un petit modèle s'en sort, comme sur l'exercice du dev container. |

Le compromis proposé : planifier avec Claude (BMAD, puis `writing-plans`), puis exécuter le plan sur `ornith-code`, de préférence dans le [dev container isolé](05-claude-code-sandbox-devcontainer.md). Cette répartition n'a **pas** été mesurée dans ce tutoriel.

---

## 8. Dépannage

| Symptôme | Cause | Remède |
|---|---|---|
| `tickets.py` répond `no active initiative` | L'initiative active est enregistrée dans `_bmad/custom/config.user.toml`, que le `.gitignore` de BMAD exclut. Ce fichier est donc **absent des worktrees**. | Passez toujours le dossier : `mark initiative-acme-salles 1.1 …` (règle du `CLAUDE.md`). |
| `bmad setup` s'arrête aussitôt | `uv` n'est pas installé. | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Claude lance `bmad-build` | Le skill est installé : sa description revendique les stories. | `npx skills remove bmad-build bmad-build-auto` |
| superpowers repart en brainstorming sur une story | La règle « entrée de ticket = design approuvé » manque dans `CLAUDE.md`, ou le prompt ne cite pas la story. | Ajoutez la règle, et citez la référence de la story (`1.2`) dans la demande. |
| `.claude/worktrees/` apparaît comme non suivi | Worktree créé par l'outil intégré de Claude Code. | Ajoutez-le au `.gitignore`. Après le merge : `git worktree remove <chemin>`, puis `git branch -d <branche>`. superpowers laisse en place les worktrees qu'il n'a pas créés lui-même. |
| Une opération Git échoue dans un worktree avec un hook qui réécrit les commandes `git` | Le hook entre en conflit avec la protection du worktree (constaté avec un proxy de réduction de sortie). | Appelez `/usr/bin/git`, ou désactivez le hook pour cette session. |
| La story reste en `review` dans `tickets.py next` | `built` est affiché comme l'état `review`. Aucun skill ne passe une story en `done` : c'est à l'humain de le faire. | `mark <initiative> <ref> done`, ou dites à `bmad-ticket` que la story est terminée. |
