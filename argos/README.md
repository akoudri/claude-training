# Argos

Argos est un petit gestionnaire de tickets : une API Node.js/Express adossée à SQLite, une
interface React (Vite) et une suite de tests Vitest.

## Démarrage rapide

Prérequis : Node.js 22.13 ou supérieur (voir `.nvmrc`). Aucune dépendance native : la base de
données utilise le module intégré `node:sqlite`.

```bash
npm install
npm run dev        # API sur http://localhost:3000 + interface sur http://localhost:5173
```

Au premier démarrage, l'API applique les migrations puis importe l'historique de l'ancien outil
de support (`data/historique.json`) dans `data/argos.db`.

## Scripts

| Commande              | Rôle                                                                 |
| --------------------- | -------------------------------------------------------------------- |
| `npm run dev`         | API (rechargement automatique) et interface en parallèle             |
| `npm start`           | API seule, qui sert aussi l'interface construite (`npm run build`)   |
| `npm test`            | Suite de tests complète (API et interface)                           |
| `npm run lint`        | Analyse statique ESLint                                              |
| `npm run build`       | Construction de l'interface dans `dist/`                             |
| `npm run db:migrate`  | Applique les migrations en attente                                   |
| `npm run db:reset`    | Recrée la base et réimporte l'historique                             |
| `npm run notif:mock`  | Lance un faux service de notification sur http://localhost:4010      |

## Organisation

```
src/api/            API Express
  app.js            assemblage de l'application (routes, statique, erreurs)
  server.js         point d'entrée : migrations, import initial, écoute HTTP
  db.js             ouverture de la base et moteur de migrations
  import.js         import de l'historique de l'ancien outil
  routes/           routes HTTP
  repositories/     accès aux données
  services/         logique métier (filtres, statistiques, notifications)
src/web/            interface React
migrations/         migrations SQL, appliquées dans l'ordre alphabétique
data/               historique à importer et base SQLite locale (non versionnée)
scripts/            scripts de développement
tests/              tests Vitest (tests/api, tests/web) et jeux de données (tests/fixtures)
```

## API

| Méthode | Route                        | Description                                           |
| ------- | ---------------------------- | ----------------------------------------------------- |
| GET     | `/api/tickets?status=…`      | Liste ; `status` vaut `open` (non clos), `closed` ou `all` |
| GET     | `/api/tickets/:id`           | Détail d'un ticket                                    |
| POST    | `/api/tickets`               | Création (`title`, `description`, `priority`)         |
| PATCH   | `/api/tickets/:id`           | Modification partielle (`status`, `priority`, …)      |
| GET     | `/api/stats`                 | Nombre de tickets par statut                          |
| GET     | `/api/health`                | Sonde de disponibilité                                |

Statuts : `open`, `in_progress`, `closed`. Priorités : `low`, `normal`, `high`.

## Notifications

Chaque création de ticket et chaque changement de statut est envoyé au service de notification
Argos. L'URL du service et sa clé d'API sont lues dans `NOTIF_API_URL` et `NOTIF_API_KEY` ; si l'une des
deux manque, les notifications sont désactivées. Pour travailler sans le vrai service, lancer
`npm run notif:mock` et reprendre les valeurs de `.env.example` dans `.env`. Une notification qui
échoue est journalisée mais ne bloque jamais l'action de l'utilisateur.

## Migrations

Les migrations sont des fichiers SQL numérotés dans `migrations/`. Une migration appliquée ne
doit plus jamais être modifiée : toute évolution du schéma passe par une nouvelle migration.
