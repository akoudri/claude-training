# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Contexte

Argos est un petit gestionnaire de tickets : API Express 5 + SQLite (`node:sqlite`, module intégré),
interface React 19 (Vite), tests Vitest. Le code, les commentaires, les messages d'erreur de l'API
et les libellés de l'interface sont en français : conserver cette convention.

## Commandes

Node.js **≥ 22.13** est obligatoire (`node:sqlite`). Sous Node 20, les tests échouent avec
`No such built-in module: node:sqlite` : basculer d'abord (`nvm use 22`).

```bash
npm install
npm run dev                  # API :3000 (rechargement auto) + Vite :5173 (proxy /api/ → :3000)
npm start                    # API seule, sert aussi dist/ si construit (npm run build)
npm test                     # toute la suite Vitest (API + interface)
npx vitest run tests/api/tickets.test.js        # un seul fichier
npx vitest run -t "change le statut"            # un seul test, par nom
npm run lint                 # ESLint (flat config, eslint.config.js)
npm run db:migrate           # applique les migrations en attente
npm run db:reset             # supprime data/argos.db, remigre, réimporte l'historique
npm run notif:mock           # faux service de notification sur :4010
```

Configuration locale : copier `.env.example` en `.env` (chargé par `src/api/env.js` via
`process.loadEnvFile`). Variables : `PORT`, `NOTIF_API_URL`, `ARGOS_DB` (chemin de la base,
défaut `data/argos.db`). Les chemins `data/…`, `dist` et `.env` sont relatifs au répertoire courant :
lancer les commandes depuis la racine d'`argos/`.

## Architecture

- **`src/api/app.js`** — `createApp({ db, notifier, staticDir })` assemble l'application sans effet
  de bord ; toutes les dépendances sont injectées. **`server.js`** est le seul point d'entrée qui a
  des effets : ouverture de la base, migrations, import initial de `data/historique.json` si la
  table `tickets` est vide, puis écoute HTTP.
- Chaîne en couches : `routes/` (validation HTTP, codes de réponse, déclenchement des notifications)
  → `repositories/tickets.js` (SQL, source de vérité des valeurs `STATUSES` / `PRIORITIES` et de la
  liste blanche `UPDATABLE`) → `services/` (logique pure : filtres, statistiques ; client de
  notification).
- Le filtrage par statut (`services/filters.js`) et les statistiques (`services/stats.js`) sont
  calculés en JavaScript sur `findAll()`, pas en SQL. Le filtre `open` signifie « non clos »
  (`open` + `in_progress`).
- **Notifications** (`services/notifier.js`) : envoyées à la création et à chaque changement de
  statut ; les routes les envoient en arrière-plan (`notifyInBackground`) : la réponse n'attend pas le service, et un échec est seulement journalisé.
  L'URL et la clé viennent de `NOTIF_API_URL` / `NOTIF_API_KEY` ; sans elles le notificateur est inactif.
- **Migrations** : fichiers SQL numérotés dans `migrations/`, appliqués par ordre alphabétique dans
  une transaction et tracés dans `schema_migrations`. Une migration déjà appliquée ne doit jamais
  être modifiée : toute évolution du schéma passe par un nouveau fichier.
- **Import** (`src/api/import.js`) : reprend l'export de l'ancien outil (champs camelCase
  `createdAt`/`updatedAt` → colonnes snake_case). L'import ramène statuts et priorités à leur forme canonique
  (`Closed` → `closed`), convertit les dates ISO au format SQLite `YYYY-MM-DD HH:MM:SS` et refuse toute valeur inconnue.
- **Interface** (`src/web/`) : `App.jsx` détient l'état (filtre, liste, stats, sélection) et
  recharge tout via un compteur `version` après chaque création ou modification ; les composants
  enfants appellent `api.js` puis `onCreated` / `onUpdated`. Les libellés français des statuts et
  priorités sont dans `labels.js` et doivent rester alignés sur `repositories/tickets.js`.

## Tests

- `tests/helpers.js` : `setup({ fixture })` crée une base `:memory:` migrée, importe une fixture de
  `tests/fixtures/` (par défaut `historique-extrait.json`, `fixture: null` pour une base vide) et
  injecte un `fakeNotifier()` dont les événements sont inspectables via `notifier.events`.
- Tests API avec `supertest` sur l'app retournée ; aucun serveur réel ni réseau.
- Tests de composants : ajouter `// @vitest-environment jsdom` en tête de fichier (l'environnement
  par défaut est `node`) et appeler `cleanup` dans `afterEach`.
