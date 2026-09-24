# Corrections issues de l'analyse d'Argos — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objectif :** corriger les défauts de sécurité, de données, de robustesse de l'API, d'outillage et
d'interface relevés lors de l'analyse du 2026-09-24, sans ajouter de fonctionnalité nouvelle.

**Architecture :** on garde le découpage existant (routes → repositories → services, `createApp`
à dépendances injectées). Les données historiques sont normalisées à l'import **et** en base par une
nouvelle migration qui ajoute des contraintes `CHECK`. Les secrets et chemins passent par
l'environnement et un module `paths.js`. Chaque correction est pilotée par un test qui échoue d'abord.

**Stack :** Node.js ≥ 22.13 (`node:sqlite`), Express 5, React 19, Vite 8, Vitest 5, supertest,
@testing-library/react.

## Contraintes globales

- Toutes les commandes se lancent depuis `argos/` avec Node 22 : `nvm use 22` (Node 20, version par défaut du poste, ne sait pas charger `node:sqlite`).
- Code, commentaires, messages d'erreur et libellés en **français**, comme le reste du projet.
- Une migration déjà appliquée (`001`, `002`) ne doit **jamais** être modifiée : toute évolution passe par un nouveau fichier.
- Aucune nouvelle dépendance npm.
- Un commit par tâche, message au format `type: description` ; chaque message se termine par la ligne
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- `npm test` et `npm run lint` doivent être verts à la fin de chaque tâche (sauf les 2 tests déjà en échec, jusqu'à la tâche 2).

## Hors périmètre (décisions à prendre séparément)

- **Authentification / autorisations, pagination, limitation de débit, en-têtes `helmet`** : ce sont
  des fonctionnalités qui demandent des choix de conception (qui sont les utilisateurs ? quel mode
  d'authentification ?). À traiter dans une session de conception dédiée. En attendant, la tâche 7
  limite l'écoute à la machine locale.
- **Actions manuelles liées à la clé divulguée** (voir tâche 1, étape finale) : révocation chez le
  fournisseur et éventuelle réécriture de l'historique git.

## Carte des fichiers

| Fichier | Tâche | Responsabilité |
|---|---|---|
| `src/api/services/notifier.js` | 1 | Clé et URL lues depuis l'environnement ; inactif sans elles |
| `scripts/notif-mock.js` | 1 | Ne plante plus sur un JSON invalide |
| `src/api/import.js` | 2, 7 | Normalisation statut/priorité/dates ; import unique (`importFileOnce`) |
| `migrations/003_normalize_tickets.sql` | 3 | Corrige les données existantes, ajoute les `CHECK` |
| `src/api/routes/tickets.js` | 4, 5, 6 | Validation des types et longueurs ; notifications en arrière-plan ; filtre SQL |
| `src/api/app.js` | 4, 6 | Gestion d'erreurs 4xx, `x-powered-by`, stats SQL |
| `src/api/repositories/tickets.js` | 6 | `findAll(db, { status })`, `countByStatus(db)` |
| `src/api/services/filters.js`, `stats.js` | 6 | **Supprimés** (remplacés par du SQL) |
| `migrations/004_create_imports.sql` | 7 | Table de suivi des imports |
| `src/api/paths.js` | 7 | Chemins absolus du projet |
| `src/api/server.js`, `env.js`, `db.js`, `scripts/*.js`, `vite.config.js` | 7 | Chemins absolus, écoute locale |
| `scripts/check-node.js`, `.npmrc`, `package.json`, `../.github/workflows/argos.yml` | 8 | Version de Node imposée, CI |
| `src/web/api.js`, `components/NewTicketForm.jsx` | 9 | Erreurs non JSON ; libellés et double envoi |
| `components/TicketList.jsx`, `TicketDetail.jsx`, `App.jsx`, `styles.css` | 10 | Clavier ; détail conservé après changement de statut |

---

### Tâche 0 : Préparation

- [ ] **Étape 1 : créer une branche de travail**

```bash
git switch -c fix/analyse-argos
```

- [ ] **Étape 2 : versionner le CLAUDE.md créé par `/init`**

```bash
git add CLAUDE.md docs/superpowers/plans/2026-09-24-corrections-analyse.md
git commit -m "docs: ajoute CLAUDE.md et le plan de corrections"
```

- [ ] **Étape 3 : constater l'état de départ**

Run: `npm test`
Expected : 17 réussis, 2 échoués (`status=open…`, `status=closed…` dans `tests/api/tickets.test.js`).

---

### Tâche 1 : Retirer la clé d'API du code (🔴 critique)

**Fichiers :**
- Modifier : `src/api/services/notifier.js`
- Modifier : `scripts/notif-mock.js:18-25`
- Modifier : `.env.example`, `README.md` (section Notifications), `CLAUDE.md` (puce Notifications)
- Test : `tests/api/notifier.test.js`

**Interfaces :**
- Produit : `createNotifier({ url?, apiKey?, fetchImpl?, logger? })` → `{ notify(event, payload): Promise<void> }`. `url` vaut par défaut `process.env.NOTIF_API_URL`, `apiKey` vaut par défaut `process.env.NOTIF_API_KEY`. Si l'un des deux manque, `notify` ne fait rien et un avertissement est journalisé une fois à la création.

- [ ] **Étape 1 : réécrire les tests du notificateur**

Remplacer tout le contenu de `tests/api/notifier.test.js` par :

```js
import { describe, it, expect, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { createNotifier } from '../../src/api/services/notifier.js';

const config = { url: 'http://notif.test', apiKey: 'ntf_test_abcdefgh' };

describe('notifier', () => {
  it("envoie l'événement au service avec la clé d'API configurée", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true });
    const notifier = createNotifier({ ...config, fetchImpl });

    await notifier.notify('ticket.created', { id: 1 });

    const [url, options] = fetchImpl.mock.calls[0];
    expect(url).toBe('http://notif.test/v1/events');
    expect(options.headers.authorization).toBe('Bearer ntf_test_abcdefgh');
    expect(JSON.parse(options.body)).toMatchObject({ event: 'ticket.created', payload: { id: 1 } });
  });

  it("n'envoie rien et prévient une fois si la clé n'est pas configurée", async () => {
    const fetchImpl = vi.fn();
    const logger = { warn: vi.fn() };
    const notifier = createNotifier({ url: 'http://notif.test', apiKey: '', fetchImpl, logger });

    await notifier.notify('ticket.created', { id: 1 });
    await notifier.notify('ticket.created', { id: 2 });

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(logger.warn).toHaveBeenCalledOnce();
  });

  it('journalise un refus du service', async () => {
    const logger = { warn: vi.fn() };
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 401 });
    const notifier = createNotifier({ ...config, fetchImpl, logger });

    await notifier.notify('ticket.created', { id: 1 });

    expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining('HTTP 401'));
  });

  it("n'échoue jamais si le service est injoignable", async () => {
    const logger = { warn: vi.fn() };
    const fetchImpl = vi.fn().mockRejectedValue(new Error('getaddrinfo ENOTFOUND'));
    const notifier = createNotifier({ ...config, fetchImpl, logger });

    await expect(notifier.notify('ticket.created', { id: 1 })).resolves.toBeUndefined();
    expect(logger.warn).toHaveBeenCalledOnce();
  });

  it('ne contient aucune clé en dur dans le code source', () => {
    const source = readFileSync(
      new URL('../../src/api/services/notifier.js', import.meta.url),
      'utf8',
    );
    expect(source).not.toMatch(/ntf_(live|test)_[a-z0-9]{8,}/);
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/notifier.test.js`
Expected : FAIL sur « clé d'API configurée » (reçoit `Bearer ntf_live_…`), « n'envoie rien… » (fetch appelé) et « aucune clé en dur ».

- [ ] **Étape 3 : implémenter**

Remplacer tout le contenu de `src/api/services/notifier.js` par :

```js
// Client du service de notification Argos (envoi d'événements aux abonnés).
// L'URL et la clé viennent de l'environnement (.env) ; sans elles, les notifications sont
// désactivées plutôt qu'envoyées vers un service par défaut.
export function createNotifier({
  url = process.env.NOTIF_API_URL,
  apiKey = process.env.NOTIF_API_KEY,
  fetchImpl = fetch,
  logger = console,
} = {}) {
  if (!url || !apiKey) {
    logger.warn('[notifier] NOTIF_API_URL ou NOTIF_API_KEY non défini : notifications désactivées');
    return { async notify() {} };
  }

  return {
    async notify(event, payload) {
      try {
        const res = await fetchImpl(`${url}/v1/events`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify({ event, payload, sentAt: new Date().toISOString() }),
          signal: AbortSignal.timeout(2000),
        });
        if (!res.ok) logger.warn(`[notifier] ${event} refusé : HTTP ${res.status}`);
      } catch (err) {
        // Une notification perdue ne doit jamais faire échouer l'action de l'utilisateur.
        logger.warn(`[notifier] ${event} non envoyé : ${err.message}`);
      }
    },
  };
}
```

- [ ] **Étape 4 : rendre le faux service robuste à un corps invalide**

Dans `scripts/notif-mock.js`, remplacer le bloc `req.on('end', …)` (lignes 20-25) par :

```js
  req.on('end', () => {
    let message;
    try {
      message = JSON.parse(body || '{}');
    } catch {
      console.log('✗ requête refusée : corps JSON invalide');
      res.writeHead(400, { 'content-type': 'application/json' }).end('{"error":"invalid json"}');
      return;
    }
    const { event, payload } = message;
    const key = auth.slice('Bearer '.length);
    console.log(`✓ ${event} ${JSON.stringify(payload)} (clé ${key.slice(0, 9)}…)`);
    res.writeHead(202, { 'content-type': 'application/json' }).end('{"accepted":true}');
  });
```

- [ ] **Étape 5 : documenter la configuration**

Remplacer tout le contenu de `.env.example` par :

```
# Copier ce fichier en .env (jamais versionné) et adapter les valeurs.
PORT=3000
# Service de notification : le vrai service, ou le faux service local (npm run notif:mock)
NOTIF_API_URL=http://localhost:4010
# Clé d'API du service. Le faux service accepte toute clé de la forme ntf_test_<8 caractères ou plus>.
# Sans URL ou sans clé, les notifications sont désactivées.
NOTIF_API_KEY=ntf_test_localdev1
```

Dans `README.md`, section « Notifications », remplacer la phrase
« Pour travailler sans le vrai service, lancer `npm run notif:mock` et renseigner
`NOTIF_API_URL=http://localhost:4010` dans `.env` (voir `.env.example`). » par :

```markdown
L'URL du service et sa clé d'API sont lues dans `NOTIF_API_URL` et `NOTIF_API_KEY` ; si l'une des
deux manque, les notifications sont désactivées. Pour travailler sans le vrai service, lancer
`npm run notif:mock` et reprendre les valeurs de `.env.example` dans `.env`.
```

Dans `CLAUDE.md`, à la fin de la puce **Notifications**, ajouter la phrase :
« L'URL et la clé viennent de `NOTIF_API_URL` / `NOTIF_API_KEY` ; sans elles le notificateur est inactif. »

- [ ] **Étape 6 : vérifier**

Run: `npx vitest run tests/api/notifier.test.js && npm run lint`
Expected : 5 tests PASS, lint sans erreur.

Vérification manuelle du faux service : `npm run notif:mock` dans un terminal, puis
`curl -s -X POST localhost:4010/v1/events -H 'authorization: Bearer ntf_test_localdev1' -d '{bad'`
→ `{"error":"invalid json"}` et le service reste en vie.

- [ ] **Étape 7 : commit**

```bash
git add src/api/services/notifier.js scripts/notif-mock.js tests/api/notifier.test.js .env.example README.md CLAUDE.md
git commit -m "fix(securite): lit la clé du service de notification depuis l'environnement"
```

- [ ] **Étape 8 : ACTIONS MANUELLES (utilisateur, hors exécution automatique)**

1. **Révoquer** la clé `ntf_live_8f3e…` chez le fournisseur du service de notification et en émettre
   une nouvelle, à placer uniquement dans le `.env` de production. La clé reste lisible dans le
   commit `f1dd984` : elle doit être considérée comme compromise.
2. Si le dépôt `github.com/akoudri/claude-training` est ou sera partagé : décider s'il faut
   réécrire l'historique (`git filter-repo --replace-text`) puis faire un push forcé. Cette opération
   est destructive et touche tout le dépôt (labs compris) : ne pas l'exécuter sans décision explicite.

---

### Tâche 2 : Normaliser l'import de l'historique

**Fichiers :**
- Modifier : `src/api/import.js`
- Créer : `tests/api/import.test.js`
- Modifier : `CLAUDE.md` (puce Import)

**Interfaces :**
- Consomme : `STATUSES`, `PRIORITIES` de `src/api/repositories/tickets.js`.
- Produit : `importTickets(db, records)` inchangé en signature ; il écrit désormais des valeurs canoniques et des dates `YYYY-MM-DD HH:MM:SS`, et lève une `Error` (sans rien importer) pour une valeur inconnue ou une date invalide.

- [ ] **Étape 1 : écrire les tests**

Créer `tests/api/import.test.js` :

```js
import { describe, it, expect } from 'vitest';
import { openDb, migrate } from '../../src/api/db.js';
import { importTickets } from '../../src/api/import.js';

function freshDb() {
  const db = openDb(':memory:');
  migrate(db);
  return db;
}

describe('importTickets', () => {
  it('normalise la casse des statuts et des priorités', () => {
    const db = freshDb();
    importTickets(db, [
      { title: 'A', status: 'Closed', priority: 'High', createdAt: '2025-11-01T10:00:00Z' },
      { title: 'B', status: ' OPEN ', createdAt: '2025-11-02T10:00:00Z' },
    ]);
    const rows = db.prepare('SELECT status, priority FROM tickets ORDER BY id').all();
    expect(rows.map((r) => ({ ...r }))).toEqual([
      { status: 'closed', priority: 'high' },
      { status: 'open', priority: 'normal' },
    ]);
  });

  it('convertit les dates ISO au format SQLite', () => {
    const db = freshDb();
    importTickets(db, [
      {
        title: 'A',
        status: 'open',
        createdAt: '2025-11-01T10:00:00Z',
        updatedAt: '2025-11-03T08:30:00Z',
      },
    ]);
    const row = db.prepare('SELECT created_at, updated_at FROM tickets').get();
    expect({ ...row }).toEqual({
      created_at: '2025-11-01 10:00:00',
      updated_at: '2025-11-03 08:30:00',
    });
  });

  it('refuse un statut inconnu sans rien importer', () => {
    const db = freshDb();
    expect(() =>
      importTickets(db, [
        { title: 'A', status: 'open', createdAt: '2025-11-01T10:00:00Z' },
        { title: 'B', status: 'wontfix', createdAt: '2025-11-01T10:00:00Z' },
      ]),
    ).toThrow(/wontfix/);
    expect(db.prepare('SELECT count(*) AS n FROM tickets').get().n).toBe(0);
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/import.test.js`
Expected : 3 FAIL (`Closed` stocké tel quel, date ISO conservée, aucune exception).

- [ ] **Étape 3 : implémenter**

Remplacer tout le contenu de `src/api/import.js` par :

```js
import { readFileSync } from 'node:fs';
import { STATUSES, PRIORITIES } from './repositories/tickets.js';

// L'ancien outil n'imposait pas la casse ('Closed', 'CLOSED', 'High'…) : chaque valeur est
// ramenée à sa forme canonique, et une valeur inconnue interrompt l'import.
function canonical(value, allowed, fallback, label, index) {
  const normalized = String(value ?? fallback).trim().toLowerCase();
  if (!allowed.includes(normalized)) {
    throw new Error(`Ticket ${index + 1} : ${label} inconnu « ${value} »`);
  }
  return normalized;
}

// '2025-11-03T09:12:00Z' → '2025-11-03 09:12:00', le format de datetime('now') dans SQLite.
function sqliteDate(iso, index) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) throw new Error(`Ticket ${index + 1} : date invalide « ${iso} »`);
  return date.toISOString().slice(0, 19).replace('T', ' ');
}

// Import de l'historique des tickets (export de l'ancien outil de support).
export function importTickets(db, records) {
  const insert = db.prepare(`INSERT INTO tickets
    (title, description, status, priority, assignee, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)`);

  db.exec('BEGIN');
  try {
    records.forEach((r, i) => {
      insert.run(
        r.title,
        r.description ?? '',
        canonical(r.status, STATUSES, 'open', 'statut', i),
        canonical(r.priority, PRIORITIES, 'normal', 'priorité', i),
        r.assignee ?? null,
        sqliteDate(r.createdAt, i),
        sqliteDate(r.updatedAt ?? r.createdAt, i),
      );
    });
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
  return records.length;
}

export function importFile(db, file) {
  return importTickets(db, JSON.parse(readFileSync(file, 'utf8')));
}
```

- [ ] **Étape 4 : vérifier**

Run: `npm test`
Expected : **tout est vert**, y compris les deux tests de filtre de `tests/api/tickets.test.js` qui échouaient (la fixture contient `Closed`).

- [ ] **Étape 5 : mettre à jour CLAUDE.md**

Dans la puce **Import**, remplacer la phrase qui commence par « Les données historiques contiennent… »
par : « L'import ramène statuts et priorités à leur forme canonique (`Closed` → `closed`), convertit
les dates ISO au format SQLite `YYYY-MM-DD HH:MM:SS` et refuse toute valeur inconnue. »

- [ ] **Étape 6 : commit**

```bash
git add src/api/import.js tests/api/import.test.js CLAUDE.md
git commit -m "fix(import): normalise statuts, priorités et dates de l'historique"
```

---

### Tâche 3 : Migration 003 — corriger les bases existantes et contraindre les valeurs

**Fichiers :**
- Créer : `migrations/003_normalize_tickets.sql`
- Modifier : `tests/api/migrations.test.js`

**Interfaces :**
- Produit : table `tickets` avec `CHECK (status IN ('open','in_progress','closed'))` et
  `CHECK (priority IN ('low','normal','high'))` ; mêmes colonnes et même numérotation qu'avant.
- Produit (tests) : helper `migrateUpTo(db, lastName)` dans `tests/api/migrations.test.js`, réutilisé en tâche 7.

- [ ] **Étape 1 : écrire les tests**

Remplacer tout le contenu de `tests/api/migrations.test.js` par :

```js
import { describe, it, expect } from 'vitest';
import { copyFileSync, mkdtempSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { openDb, migrate, MIGRATIONS_DIR } from '../../src/api/db.js';

// Applique les migrations jusqu'à `last` incluse, pour simuler une base créée avant les suivantes.
function migrateUpTo(db, last) {
  const dir = mkdtempSync(join(tmpdir(), 'argos-migrations-'));
  for (const name of readdirSync(MIGRATIONS_DIR)) {
    if (name.endsWith('.sql') && name <= last) copyFileSync(join(MIGRATIONS_DIR, name), join(dir, name));
  }
  migrate(db, dir);
}

describe('migrations', () => {
  it("s'appliquent dans l'ordre sur une base vide", () => {
    const db = openDb(':memory:');
    const applied = migrate(db);
    expect(applied[0]).toBe('001_create_tickets.sql');
    expect(applied).toEqual([...applied].sort());
  });

  it('ne sont pas rejouées une seconde fois', () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(migrate(db)).toEqual([]);
  });
});

describe('003 — normalisation des tickets', () => {
  it('corrige les valeurs et les dates déjà importées', () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '002_add_assignee.sql');
    db.prepare(
      `INSERT INTO tickets (title, status, priority, created_at, updated_at)
       VALUES ('A', 'Closed', 'High', '2025-11-01T10:00:00Z', '2025-11-02T10:00:00Z')`,
    ).run();

    migrate(db);

    const row = db.prepare('SELECT id, status, priority, created_at, updated_at FROM tickets').get();
    expect({ ...row }).toEqual({
      id: 1,
      status: 'closed',
      priority: 'high',
      created_at: '2025-11-01 10:00:00',
      updated_at: '2025-11-02 10:00:00',
    });
  });

  it('ne réattribue pas le numéro d’un ticket supprimé', () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '002_add_assignee.sql');
    db.exec("INSERT INTO tickets (title) VALUES ('A'), ('B'), ('C')");
    db.exec('DELETE FROM tickets WHERE id = 3');

    migrate(db);
    const { lastInsertRowid } = db.prepare("INSERT INTO tickets (title) VALUES ('D')").run();

    expect(Number(lastInsertRowid)).toBe(4);
  });

  it('refuse un statut ou une priorité hors liste', () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(() => db.prepare("INSERT INTO tickets (title, status) VALUES ('A', 'Closed')").run()).toThrow(/CHECK/);
    expect(() => db.prepare("INSERT INTO tickets (title, priority) VALUES ('A', 'urgent')").run()).toThrow(/CHECK/);
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/migrations.test.js`
Expected : FAIL sur « corrige les valeurs… » et « refuse un statut… » (le test de numérotation peut déjà passer).

- [ ] **Étape 3 : écrire la migration**

Créer `migrations/003_normalize_tickets.sql` (SQL vérifié sur une base de test pendant l'analyse) :

```sql
-- 003 — Normalisation des données importées et contraintes sur les valeurs autorisées
UPDATE tickets SET status = lower(trim(status)), priority = lower(trim(priority));
UPDATE tickets SET created_at = replace(substr(created_at, 1, 19), 'T', ' ')
  WHERE created_at LIKE '____-__-__T%';
UPDATE tickets SET updated_at = replace(substr(updated_at, 1, 19), 'T', ' ')
  WHERE updated_at LIKE '____-__-__T%';

-- SQLite ne sait pas ajouter une contrainte CHECK à une table existante : on la reconstruit.
CREATE TABLE tickets_new (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT    NOT NULL,
  description TEXT    NOT NULL DEFAULT '',
  status      TEXT    NOT NULL DEFAULT 'open'   CHECK (status IN ('open', 'in_progress', 'closed')),
  priority    TEXT    NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  assignee    TEXT
);
INSERT INTO tickets_new (id, title, description, status, priority, created_at, updated_at, assignee)
  SELECT id, title, description, status, priority, created_at, updated_at, assignee FROM tickets;

-- Conserve le compteur AUTOINCREMENT : un numéro de ticket supprimé ne doit pas être réattribué.
DELETE FROM sqlite_sequence WHERE name = 'tickets_new';
INSERT INTO sqlite_sequence (name, seq) SELECT 'tickets_new', seq FROM sqlite_sequence WHERE name = 'tickets';

DROP TABLE tickets;
ALTER TABLE tickets_new RENAME TO tickets;
```

- [ ] **Étape 4 : vérifier**

Run: `npm test`
Expected : tout PASS.

Vérification sur la vraie base locale (si `data/argos.db` existe) :
`npm run db:migrate` → « Migrations appliquées : 003_normalize_tickets.sql », puis
`curl -s localhost:3000/api/stats` (API lancée) → la somme `open + in_progress + closed` égale `total` (18).

- [ ] **Étape 5 : commit**

```bash
git add migrations/003_normalize_tickets.sql tests/api/migrations.test.js
git commit -m "fix(db): migration 003, normalise les tickets et ajoute des contraintes CHECK"
```

---

### Tâche 4 : Valider les types et les longueurs, corriger la gestion d'erreurs

**Fichiers :**
- Modifier : `src/api/routes/tickets.js`
- Modifier : `src/api/app.js`
- Modifier : `tests/api/tickets.test.js` (ajouts en fin de fichier)
- Créer : `tests/api/app.test.js`

**Interfaces :**
- Produit : réponses **400** `{ error: <message français> }` pour une description qui n'est pas un texte, un responsable qui n'est ni un texte ni `null`, ou un titre de plus de 200, une description de plus de 5000 ou un responsable de plus de 100 caractères. Toute erreur 4xx venue d'Express (JSON mal formé, corps trop gros) → `{ error: 'Requête invalide' }` avec son code d'origine.

- [ ] **Étape 1 : écrire les tests de validation**

Ajouter à la fin de `tests/api/tickets.test.js` :

```js
describe('validation des champs', () => {
  it.each([
    ['une description non textuelle', { title: 'x', description: { a: 1 } }],
    ['un responsable non textuel', { title: 'x', assignee: ['camille'] }],
    ['un titre trop long', { title: 'x'.repeat(201) }],
    ['une description trop longue', { title: 'x', description: 'x'.repeat(5001) }],
  ])('POST refuse %s avec 400', async (_label, body) => {
    const { app } = setup({ fixture: null });
    const res = await request(app).post('/api/tickets').send(body);
    expect(res.status).toBe(400);
    expect(res.body.error).toBeTruthy();
  });

  it('PATCH accepte de retirer le responsable', async () => {
    const { app } = setup();
    await request(app).patch('/api/tickets/1').send({ assignee: 'camille' });
    const res = await request(app).patch('/api/tickets/1').send({ assignee: null });
    expect(res.status).toBe(200);
    expect(res.body.assignee).toBeNull();
  });

  it('PATCH retire les espaces autour du titre', async () => {
    const { app } = setup();
    const res = await request(app).patch('/api/tickets/1').send({ title: '  Nouveau titre  ' });
    expect(res.body.title).toBe('Nouveau titre');
  });
});
```

Créer `tests/api/app.test.js` :

```js
import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { setup } from '../helpers.js';

describe("gestion des erreurs de l'application", () => {
  it('répond 400 à un corps JSON mal formé', async () => {
    const { app } = setup({ fixture: null });
    const res = await request(app)
      .post('/api/tickets')
      .set('content-type', 'application/json')
      .send('{mal formé');
    expect(res.status).toBe(400);
    expect(res.body).toEqual({ error: 'Requête invalide' });
  });

  it("n'expose pas la technologie du serveur", async () => {
    const { app } = setup({ fixture: null });
    const res = await request(app).get('/api/health');
    expect(res.headers['x-powered-by']).toBeUndefined();
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/tickets.test.js tests/api/app.test.js`
Expected : FAIL pour les 4 cas `POST refuse…` (500 au lieu de 400), `retire les espaces`, `JSON mal formé` (500) et `x-powered-by` (`Express`). « retirer le responsable » passe déjà : il protège contre une régression.

- [ ] **Étape 3 : implémenter la validation**

Dans `src/api/routes/tickets.js`, remplacer la fonction `validate` (lignes 9-20) par :

```js
const MAX_LENGTH = { title: 200, description: 5000, assignee: 100 };

function validate(body, { partial }) {
  if (!partial || body.title !== undefined) {
    if (typeof body.title !== 'string' || body.title.trim() === '') return 'Le titre est obligatoire';
  }
  if (body.description !== undefined && typeof body.description !== 'string') {
    return 'La description doit être un texte';
  }
  if (body.assignee !== undefined && body.assignee !== null && typeof body.assignee !== 'string') {
    return 'Le responsable doit être un texte ou null';
  }
  for (const [field, max] of Object.entries(MAX_LENGTH)) {
    if (typeof body[field] === 'string' && body[field].length > max) {
      return `Le champ ${field} dépasse ${max} caractères`;
    }
  }
  if (body.status !== undefined && !tickets.STATUSES.includes(body.status)) {
    return `Statut invalide (attendu : ${tickets.STATUSES.join(', ')})`;
  }
  if (body.priority !== undefined && !tickets.PRIORITIES.includes(body.priority)) {
    return `Priorité invalide (attendu : ${tickets.PRIORITIES.join(', ')})`;
  }
  return null;
}
```

Dans la route `PATCH`, remplacer `const after = tickets.update(db, id, req.body);` par :

```js
    const changes = { ...req.body };
    if (typeof changes.title === 'string') changes.title = changes.title.trim();
    const after = tickets.update(db, id, changes);
```

- [ ] **Étape 4 : implémenter la gestion d'erreurs**

Dans `src/api/app.js`, remplacer `app.use(express.json());` par :

```js
  app.disable('x-powered-by');
  app.use(express.json({ limit: '64kb' }));
```

et remplacer le gestionnaire d'erreurs final par :

```js
  // Les erreurs 4xx d'Express (JSON mal formé, corps trop volumineux…) gardent leur code ;
  // seules les vraies erreurs serveur sont journalisées.
  app.use((err, req, res, _next) => {
    const status = err.status ?? err.statusCode ?? 500;
    if (status >= 500) {
      console.error(err);
      return res.status(500).json({ error: 'Erreur interne' });
    }
    res.status(status).json({ error: 'Requête invalide' });
  });
```

- [ ] **Étape 5 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS.

- [ ] **Étape 6 : commit**

```bash
git add src/api/routes/tickets.js src/api/app.js tests/api/tickets.test.js tests/api/app.test.js
git commit -m "fix(api): valide types et longueurs, renvoie 400 sur requête mal formée"
```

---

### Tâche 5 : Envoyer les notifications sans bloquer la réponse

**Fichiers :**
- Modifier : `src/api/routes/tickets.js`
- Créer : `tests/api/notifications.test.js`
- Modifier : `CLAUDE.md` (puce Notifications)

**Interfaces :**
- Consomme : `notifier.notify(event, payload): Promise<void>` (tâche 1).
- Produit : les routes POST et PATCH répondent sans attendre `notify`. Les événements de `fakeNotifier()` restent visibles juste après la requête, car son `push` s'exécute avant tout `await`.

- [ ] **Étape 1 : écrire le test**

Créer `tests/api/notifications.test.js` :

```js
import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { openDb, migrate } from '../../src/api/db.js';
import { createApp } from '../../src/api/app.js';

// Notificateur qui ne répond jamais : simule un service de notification bloqué.
function stuckApp() {
  const db = openDb(':memory:');
  migrate(db);
  return createApp({ db, notifier: { notify: () => new Promise(() => {}) } });
}

describe('notifications', () => {
  it("la création ne dépend pas du temps de réponse du service", async () => {
    const res = await request(stuckApp()).post('/api/tickets').send({ title: 'x' });
    expect(res.status).toBe(201);
  }, 1000);

  it('le changement de statut ne dépend pas du temps de réponse du service', async () => {
    const app = stuckApp();
    await request(app).post('/api/tickets').send({ title: 'x' });
    const res = await request(app).patch('/api/tickets/1').send({ status: 'closed' });
    expect(res.status).toBe(200);
  }, 1000);
});
```

Note : le premier test ne peut pas passer tant que la création attend la notification. Le second
dépend de la création, il échoue donc aussi par délai dépassé.

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/notifications.test.js`
Expected : 2 FAIL « Test timed out in 1000ms ».

- [ ] **Étape 3 : implémenter**

Dans `src/api/routes/tickets.js`, ajouter après `badRequest` :

```js
// Envoi en arrière-plan : la réponse à l'utilisateur n'attend pas le service de notification.
function notifyInBackground(notifier, event, payload) {
  notifier.notify(event, payload).catch((err) => console.warn(`[notifier] ${event} : ${err.message}`));
}
```

Dans la route `POST`, retirer `async` du gestionnaire et remplacer
`await notifier.notify('ticket.created', { id: ticket.id, title: ticket.title });` par :

```js
    notifyInBackground(notifier, 'ticket.created', { id: ticket.id, title: ticket.title });
```

Dans la route `PATCH`, retirer `async` du gestionnaire et remplacer
`await notifier.notify('ticket.status_changed', { id, from: before.status, to: after.status });` par :

```js
      notifyInBackground(notifier, 'ticket.status_changed', { id, from: before.status, to: after.status });
```

- [ ] **Étape 4 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS, y compris les tests d'événements existants de `tickets.test.js`.

- [ ] **Étape 5 : mettre à jour CLAUDE.md**

Dans la puce **Notifications**, remplacer « un échec est journalisé mais ne doit jamais faire échouer
la requête utilisateur. » par « les routes les envoient en arrière-plan (`notifyInBackground`) : la
réponse n'attend pas le service, et un échec est seulement journalisé. »

- [ ] **Étape 6 : commit**

```bash
git add src/api/routes/tickets.js tests/api/notifications.test.js CLAUDE.md
git commit -m "perf(api): envoie les notifications sans retarder la réponse"
```

---

### Tâche 6 : Filtres et statistiques en SQL (priorité basse)

**Fichiers :**
- Modifier : `src/api/repositories/tickets.js`, `src/api/routes/tickets.js`, `src/api/app.js`
- Supprimer : `src/api/services/filters.js`, `src/api/services/stats.js`
- Modifier : `tests/api/stats.test.js`, `tests/api/tickets.test.js`, `CLAUDE.md`

**Interfaces :**
- Produit : `findAll(db, { status = 'all' } = {})`, qui renvoie les tickets triés par `id`. `status` vaut `'open'` (non clos), `'closed'`, ou toute autre valeur pour tout renvoyer.
- Produit : `countByStatus(db)`, qui renvoie `{ total, open, in_progress, closed }`.

- [ ] **Étape 1 : ajouter les tests garde-fous**

Ajouter dans le `describe` de `tests/api/stats.test.js` :

```js
  it("compte les tickets importés de l'ancien outil", async () => {
    const { app } = setup();
    const res = await request(app).get('/api/stats');
    expect(res.body).toEqual({ total: 4, open: 1, in_progress: 1, closed: 2 });
  });
```

Ajouter dans le `describe('GET /api/tickets')` de `tests/api/tickets.test.js` :

```js
  it('renvoie tous les tickets pour un filtre inconnu', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets?status=constructor');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(4);
  });
```

- [ ] **Étape 2 : constater qu'ils passent avant le remaniement**

Run: `npx vitest run tests/api/stats.test.js tests/api/tickets.test.js`
Expected : PASS. Ces tests fixent le comportement à préserver pendant le remaniement.

- [ ] **Étape 3 : implémenter**

Dans `src/api/repositories/tickets.js`, remplacer `findAll` par :

```js
// Filtres de liste : open = non clos (ouverts ou en cours), closed = clos, sinon tout.
const STATUS_FILTERS = {
  open: "WHERE status <> 'closed'",
  closed: "WHERE status = 'closed'",
};

export function findAll(db, { status = 'all' } = {}) {
  const where = Object.hasOwn(STATUS_FILTERS, status) ? STATUS_FILTERS[status] : '';
  return db.prepare(`SELECT * FROM tickets ${where} ORDER BY id`).all();
}

// Compteurs affichés dans l'en-tête de l'interface.
export function countByStatus(db) {
  const counts = { total: 0 };
  for (const status of STATUSES) counts[status] = 0;
  for (const { status, n } of db.prepare('SELECT status, count(*) AS n FROM tickets GROUP BY status').all()) {
    counts[status] = n;
    counts.total += n;
  }
  return counts;
}
```

Dans `src/api/routes/tickets.js` : supprimer l'import de `filterByStatus` et remplacer le corps de
`router.get('/')` par `res.json(tickets.findAll(db, { status: req.query.status }));`.

Dans `src/api/app.js` : remplacer les deux imports `findAll` / `countByStatus` par
`import { countByStatus } from './repositories/tickets.js';` et la route stats par
`app.get('/api/stats', (req, res) => res.json(countByStatus(db)));`.

Supprimer les fichiers devenus inutiles :

```bash
git rm src/api/services/filters.js src/api/services/stats.js
```

- [ ] **Étape 4 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS, lint sans import inutilisé.

- [ ] **Étape 5 : mettre à jour CLAUDE.md**

Remplacer la puce qui commence par « Le filtrage par statut (`services/filters.js`) » par :
« Le filtrage par statut et les statistiques sont faits en SQL dans `repositories/tickets.js`
(`findAll(db, { status })`, `countByStatus(db)`). Le filtre `open` signifie « non clos »
(`open` + `in_progress`). » Retirer aussi « filtres, statistiques » de la description de `services/`.

- [ ] **Étape 6 : commit**

```bash
git add -A src/api tests/api CLAUDE.md
git commit -m "refactor(api): filtres et statistiques calculés en SQL"
```

---

### Tâche 7 : Import unique, chemins absolus, écoute locale

**Fichiers :**
- Créer : `migrations/004_create_imports.sql`, `src/api/paths.js`
- Modifier : `src/api/import.js`, `src/api/db.js`, `src/api/env.js`, `src/api/server.js`
- Modifier : `scripts/migrate.js`, `scripts/reset-db.js`, `vite.config.js`
- Modifier : `tests/api/import.test.js`, `tests/api/migrations.test.js`
- Modifier : `.env.example`, `README.md`, `CLAUDE.md`

**Interfaces :**
- Consomme : `importTickets(db, records)` (tâche 2), `migrateUpTo` (tâche 3).
- Produit : `importFileOnce(db, file)` renvoie le nombre de tickets importés, ou `null` si ce fichier
  (identifié par son nom de base) a déjà été importé. Remplace `importFile`, qui est supprimé.
- Produit : `src/api/paths.js` exporte `ROOT_DIR`, `ENV_FILE`, `DIST_DIR`, `HISTORY_FILE`, `MIGRATIONS_DIR` (chemins absolus).

- [ ] **Étape 1 : écrire les tests**

Ajouter à la fin de `tests/api/import.test.js` (et compléter les imports en tête :
`import { fileURLToPath } from 'node:url';` et `importFileOnce` depuis `../../src/api/import.js`) :

```js
describe('importFileOnce', () => {
  const file = fileURLToPath(new URL('../fixtures/historique-extrait.json', import.meta.url));

  it("importe un fichier la première fois, puis l'ignore même si la base a été vidée", () => {
    const db = freshDb();
    expect(importFileOnce(db, file)).toBe(4);

    db.exec('DELETE FROM tickets');

    expect(importFileOnce(db, file)).toBeNull();
    expect(db.prepare('SELECT count(*) AS n FROM tickets').get().n).toBe(0);
  });
});
```

Ajouter à la fin de `tests/api/migrations.test.js` :

```js
describe('004 — suivi des imports', () => {
  it("considère l'historique comme déjà importé sur une base qui contient des tickets", () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '003_normalize_tickets.sql');
    db.exec("INSERT INTO tickets (title) VALUES ('A')");

    migrate(db);

    expect(db.prepare('SELECT name FROM imports').all().map((r) => r.name)).toEqual(['historique.json']);
  });

  it("ne marque rien sur une base neuve", () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(db.prepare('SELECT count(*) AS n FROM imports').get().n).toBe(0);
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/api/import.test.js tests/api/migrations.test.js`
Expected : FAIL (`importFileOnce` n'existe pas, table `imports` absente).

- [ ] **Étape 3 : migration 004**

Créer `migrations/004_create_imports.sql` :

```sql
-- 004 — Suivi des imports réalisés : l'historique n'est importé qu'une fois, même si la base se vide.
CREATE TABLE imports (
  name        TEXT PRIMARY KEY,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les bases existantes ont déjà reçu l'historique lors de leur premier démarrage.
INSERT INTO imports (name) SELECT 'historique.json' WHERE EXISTS (SELECT 1 FROM tickets);
```

- [ ] **Étape 4 : `importFileOnce`**

Dans `src/api/import.js` :
- ajouter `import { basename } from 'node:path';` en tête ;
- changer la signature en `export function importTickets(db, records, { name } = {})` et, juste
  après `db.exec('BEGIN');` puis `try {`, ajouter :

```js
    if (name) db.prepare('INSERT INTO imports (name) VALUES (?)').run(name);
```

- remplacer `importFile` par :

```js
// Importe un fichier d'historique s'il ne l'a jamais été (suivi dans la table imports).
// Renvoie le nombre de tickets importés, ou null si le fichier avait déjà été importé.
export function importFileOnce(db, file) {
  const name = basename(file);
  if (db.prepare('SELECT 1 FROM imports WHERE name = ?').get(name)) return null;
  return importTickets(db, JSON.parse(readFileSync(file, 'utf8')), { name });
}
```

- [ ] **Étape 5 : chemins absolus**

Créer `src/api/paths.js` :

```js
// Chemins absolus du projet : l'API et les scripts fonctionnent quel que soit le répertoire courant.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT_DIR = fileURLToPath(new URL('../../', import.meta.url));
export const ENV_FILE = join(ROOT_DIR, '.env');
export const DIST_DIR = join(ROOT_DIR, 'dist');
export const HISTORY_FILE = join(ROOT_DIR, 'data/historique.json');
export const MIGRATIONS_DIR = join(ROOT_DIR, 'migrations');
```

Dans `src/api/db.js`, remplacer les imports de `node:path` / `node:url` et les deux constantes
(lignes 3-7) par :

```js
import { dirname, join } from 'node:path';
import { MIGRATIONS_DIR, ROOT_DIR } from './paths.js';

export { MIGRATIONS_DIR };
export const DEFAULT_DB_FILE = process.env.ARGOS_DB ?? join(ROOT_DIR, 'data/argos.db');
```

Remplacer tout le contenu de `src/api/env.js` par :

```js
// Charge .env s'il existe. Importé en premier par server.js et les scripts, avant tout module qui
// lit process.env au chargement.
import { existsSync } from 'node:fs';
import { ENV_FILE } from './paths.js';

if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);
```

- [ ] **Étape 6 : serveur, scripts, proxy**

Remplacer tout le contenu de `src/api/server.js` par :

```js
import './env.js';
import { createApp } from './app.js';
import { openDb, migrate } from './db.js';
import { importFileOnce } from './import.js';
import { DIST_DIR, HISTORY_FILE } from './paths.js';
import { createNotifier } from './services/notifier.js';

const PORT = Number(process.env.PORT ?? 3000);
// L'API n'a pas d'authentification : par défaut, elle n'est joignable que depuis la machine locale.
const HOST = process.env.HOST ?? '127.0.0.1';

const db = openDb();
const applied = migrate(db);
if (applied.length) console.log(`Migrations appliquées : ${applied.join(', ')}`);

// Première exécution : on reprend l'historique de l'ancien outil, une seule fois.
const imported = importFileOnce(db, HISTORY_FILE);
if (imported !== null) console.log(`Import de l'historique : ${imported} tickets`);

const app = createApp({ db, notifier: createNotifier(), staticDir: DIST_DIR });
app.listen(PORT, HOST, () => console.log(`Argos API sur http://${HOST}:${PORT}`));
```

Remplacer tout le contenu de `scripts/migrate.js` par :

```js
import '../src/api/env.js';
import { openDb, migrate } from '../src/api/db.js';

const applied = migrate(openDb());
console.log(applied.length ? `Migrations appliquées : ${applied.join(', ')}` : 'Base à jour.');
```

Remplacer tout le contenu de `scripts/reset-db.js` par :

```js
import '../src/api/env.js';
import { rmSync } from 'node:fs';
import { DEFAULT_DB_FILE, openDb, migrate } from '../src/api/db.js';
import { importFileOnce } from '../src/api/import.js';
import { HISTORY_FILE } from '../src/api/paths.js';

rmSync(DEFAULT_DB_FILE, { force: true });
const db = openDb();
console.log(`Migrations appliquées : ${migrate(db).join(', ')}`);
console.log(`Import de l'historique : ${importFileOnce(db, HISTORY_FILE)} tickets`);
```

Dans `vite.config.js`, remplacer `proxy: { '/api/': 'http://localhost:3000' },` par
`proxy: { '/api/': 'http://127.0.0.1:3000' },`. Sinon, `localhost` peut se résoudre en `::1` alors
que l'API n'écoute qu'en IPv4.

Dans `.env.example`, ajouter après `PORT=3000` :

```
# Adresse d'écoute de l'API : 127.0.0.1 = machine locale uniquement (l'API n'a pas d'authentification)
HOST=127.0.0.1
```

- [ ] **Étape 7 : documentation**

Dans `README.md`, remplacer « Au premier démarrage, l'API applique les migrations puis importe
l'historique de l'ancien outil de support (`data/historique.json`) dans `data/argos.db`. » par :

```markdown
Au premier démarrage, l'API applique les migrations puis importe une seule fois l'historique de
l'ancien outil de support (`data/historique.json`) dans `data/argos.db`. Par défaut elle n'écoute que
sur `127.0.0.1` (variable `HOST`), car elle n'a pas d'authentification.
```

Dans `CLAUDE.md` :
- section Commandes, remplacer « Les chemins `data/…`, `dist` et `.env` sont relatifs au répertoire
  courant : lancer les commandes depuis la racine d'`argos/`. » par « Tous les chemins sont absolus
  (`src/api/paths.js`) ; `HOST` (défaut `127.0.0.1`) règle l'adresse d'écoute. » ;
- puce `server.js`, remplacer « import initial de `data/historique.json` si la table `tickets` est
  vide » par « import unique de `data/historique.json` (`importFileOnce`, suivi dans la table
  `imports`) ».

- [ ] **Étape 8 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS.

Vérification manuelle depuis un autre répertoire :

```bash
cd /tmp && ARGOS_DB=/tmp/argos-verif.db PORT=3999 node --disable-warning=ExperimentalWarning ~/Training/claude-training/argos/src/api/server.js
```

Expected : « Migrations appliquées : 001…004 », « Import de l'historique : 18 tickets »,
« Argos API sur http://127.0.0.1:3999 ». Dans un autre terminal :
`curl -s 127.0.0.1:3999/api/stats` → `{"total":18,…}` avec une somme cohérente. Arrêter, relancer :
aucune ligne « Import ». Enfin `rm /tmp/argos-verif.db`.

- [ ] **Étape 9 : commit**

```bash
git add migrations/004_create_imports.sql src/api scripts vite.config.js tests/api .env.example README.md CLAUDE.md
git commit -m "fix(api): import unique de l'historique, chemins absolus, écoute locale par défaut"
```

---

### Tâche 8 : Imposer la version de Node et ajouter la CI

**Fichiers :**
- Créer : `scripts/check-node.js`, `.npmrc`, `../.github/workflows/argos.yml` (à la racine du dépôt `claude-training`)
- Modifier : `package.json` (scripts)

- [ ] **Étape 1 : script de contrôle**

Créer `scripts/check-node.js` :

```js
// Vérifie la version de Node avant les tests et le lancement : node:sqlite exige Node 22.13.
const [major, minor] = process.versions.node.split('.').map(Number);
if (major < 22 || (major === 22 && minor < 13)) {
  console.error(`Argos exige Node.js >= 22.13 (version actuelle : ${process.version}). Lancer : nvm use 22`);
  process.exit(1);
}
```

Dans `package.json`, ajouter à `scripts` (npm exécute automatiquement les scripts `pre*`) :

```json
    "predev": "node scripts/check-node.js",
    "prestart": "node scripts/check-node.js",
    "pretest": "node scripts/check-node.js",
```

Créer `.npmrc` :

```
engine-strict=true
```

- [ ] **Étape 2 : vérifier le refus sous Node 20**

Run: `PATH=$HOME/.nvm/versions/node/v20.16.0/bin:$PATH npm test`
Expected : « Argos exige Node.js >= 22.13 (version actuelle : v20.16.0)… », code de sortie 1, aucun test lancé.

Run (Node 22) : `npm test`
Expected : tout PASS.

- [ ] **Étape 3 : CI GitHub Actions**

Créer `/home/ali/Training/claude-training/.github/workflows/argos.yml` :

```yaml
name: argos

on:
  push:
    paths: ['argos/**', '.github/workflows/argos.yml']
  pull_request:
    paths: ['argos/**', '.github/workflows/argos.yml']

jobs:
  verifier:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: argos
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version-file: argos/.nvmrc
          cache: npm
          cache-dependency-path: argos/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

- [ ] **Étape 4 : commit**

```bash
git add scripts/check-node.js .npmrc package.json ../.github/workflows/argos.yml
git commit -m "chore: impose Node 22.13 et ajoute la CI (lint, tests, build)"
```

La CI ne s'exécutera qu'après un push sur GitHub, qui reste à la décision de l'utilisateur.

---

### Tâche 9 : Interface — erreurs non JSON, formulaire accessible, pas de double envoi

**Fichiers :**
- Modifier : `src/web/api.js`, `src/web/components/NewTicketForm.jsx`
- Créer : `tests/web/api.test.js`, `tests/web/NewTicketForm.test.jsx`

**Interfaces :**
- Produit : `api.*` rejette avec `Error(body.error)` si la réponse JSON en contient un, sinon avec `Error('HTTP <code>')`, y compris quand le corps n'est pas du JSON.
- Produit : champs du formulaire accessibles par leur libellé : « Titre », « Description », « Priorité ».

- [ ] **Étape 1 : écrire les tests**

Créer `tests/web/api.test.js` :

```js
import { describe, it, expect, vi, afterEach } from 'vitest';
import { api } from '../../src/web/api.js';

afterEach(() => vi.unstubAllGlobals());

function stubFetch(status, text) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(text, { status })));
}

describe('client API', () => {
  it("remonte le message d'erreur renvoyé par l'API", async () => {
    stubFetch(400, '{"error":"Le titre est obligatoire"}');
    await expect(api.createTicket({ title: '' })).rejects.toThrow('Le titre est obligatoire');
  });

  it("indique le code HTTP quand la réponse n'est pas du JSON", async () => {
    stubFetch(502, '<html>Bad Gateway</html>');
    await expect(api.getStats()).rejects.toThrow('HTTP 502');
  });
});
```

Créer `tests/web/NewTicketForm.test.jsx` :

```jsx
// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import NewTicketForm from '../../src/web/components/NewTicketForm.jsx';
import { api } from '../../src/web/api.js';

vi.mock('../../src/web/api.js', () => ({ api: { createTicket: vi.fn() } }));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('<NewTicketForm>', () => {
  it('associe un libellé à chaque champ', () => {
    render(<NewTicketForm onCreated={() => {}} />);
    expect(screen.getByLabelText('Titre')).toBeTruthy();
    expect(screen.getByLabelText('Description')).toBeTruthy();
    expect(screen.getByLabelText('Priorité')).toBeTruthy();
  });

  it("n'envoie qu'une création en cas de double clic", async () => {
    let resolve;
    api.createTicket.mockReturnValue(new Promise((r) => (resolve = r)));
    const onCreated = vi.fn();
    render(<NewTicketForm onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText('Titre'), { target: { value: 'Panne' } });
    const button = screen.getByRole('button', { name: 'Créer' });
    fireEvent.click(button);
    fireEvent.click(button);

    expect(api.createTicket).toHaveBeenCalledOnce();
    resolve({ id: 1 });
    await vi.waitFor(() => expect(onCreated).toHaveBeenCalledOnce());
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/web/api.test.js tests/web/NewTicketForm.test.jsx`
Expected : FAIL « HTTP 502 » (erreur de parsing JSON à la place), FAIL libellés introuvables, FAIL double appel.

- [ ] **Étape 3 : implémenter `api.js`**

Dans `src/web/api.js`, remplacer les lignes 6-8 (`const body = await res.json();` … `return body;`) par :

```js
  // Un proxy ou une page d'erreur peut renvoyer autre chose que du JSON.
  const text = await res.text();
  let body = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    if (res.ok) throw new Error('Réponse invalide du serveur');
  }
  if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body;
```

- [ ] **Étape 4 : implémenter le formulaire**

Remplacer tout le contenu de `src/web/components/NewTicketForm.jsx` par :

```jsx
import { useState } from 'react';
import { api } from '../api.js';
import { PRIORITY_LABELS } from '../labels.js';

export default function NewTicketForm({ onCreated }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('normal');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await api.createTicket({ title, description, priority });
      setTitle('');
      setDescription('');
      setPriority('normal');
      setError(null);
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="new-ticket" onSubmit={submit}>
      <h3>Nouveau ticket</h3>
      <label htmlFor="new-ticket-title">Titre</label>
      <input id="new-ticket-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <label htmlFor="new-ticket-description">Description</label>
      <textarea
        id="new-ticket-description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <label htmlFor="new-ticket-priority">Priorité</label>
      <select id="new-ticket-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
        {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <button type="submit" disabled={submitting}>
        Créer
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
```

- [ ] **Étape 5 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS.

- [ ] **Étape 6 : commit**

```bash
git add src/web/api.js src/web/components/NewTicketForm.jsx tests/web/api.test.js tests/web/NewTicketForm.test.jsx
git commit -m "fix(web): erreurs non JSON, libellés du formulaire, pas de double création"
```

---

### Tâche 10 : Interface — liste utilisable au clavier, détail conservé après changement de statut

**Fichiers :**
- Modifier : `src/web/components/TicketList.jsx`, `src/web/components/TicketDetail.jsx`, `src/web/App.jsx`, `src/web/styles.css`
- Modifier : `tests/web/TicketList.test.jsx`
- Créer : `tests/web/App.test.jsx`

**Interfaces :**
- Consomme : `api.updateTicket(id, changes)`, qui renvoie le ticket modifié (réponse de `PATCH`).
- Produit : `TicketDetail` appelle `onUpdated(ticketModifié)`. `App` garde l'objet du ticket sélectionné (`selected`) au lieu de le rechercher dans la liste filtrée.

- [ ] **Étape 1 : écrire les tests**

Ajouter dans le `describe` de `tests/web/TicketList.test.jsx` :

```jsx
  it('se sélectionne au clavier', () => {
    const onSelect = vi.fn();
    render(<TicketList tickets={tickets} onSelect={onSelect} />);
    const item = screen.getByRole('button', { name: /Second/ });
    fireEvent.keyDown(item, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(2);
  });
```

Créer `tests/web/App.test.jsx` :

```jsx
// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import App from '../../src/web/App.jsx';
import { api } from '../../src/web/api.js';

vi.mock('../../src/web/api.js', () => ({
  api: { listTickets: vi.fn(), getStats: vi.fn(), createTicket: vi.fn(), updateTicket: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

const ticket = {
  id: 1,
  title: 'Panne',
  description: '',
  status: 'open',
  priority: 'normal',
  assignee: null,
  created_at: '2026-09-24 10:00:00',
};

describe('<App>', () => {
  it('garde le détail affiché quand le ticket est clos sous le filtre « Ouverts »', async () => {
    api.getStats.mockResolvedValue({ total: 1, open: 1, in_progress: 0, closed: 0 });
    api.listTickets.mockResolvedValueOnce([ticket]).mockResolvedValue([]);
    api.updateTicket.mockResolvedValue({ ...ticket, status: 'closed' });
    render(<App />);

    fireEvent.click(await screen.findByText('Panne'));
    fireEvent.change(screen.getByLabelText(/Statut/), { target: { value: 'closed' } });

    expect(await screen.findByText('Aucun ticket.')).toBeTruthy();
    expect(screen.getByRole('heading', { name: /#1 — Panne/ })).toBeTruthy();
  });
});
```

- [ ] **Étape 2 : vérifier l'échec**

Run: `npx vitest run tests/web`
Expected : FAIL « se sélectionne au clavier » (aucun rôle `button`), FAIL sur le test `<App>` (le détail est remplacé par « Sélectionner un ticket… »).

- [ ] **Étape 3 : liste accessible au clavier**

Dans `src/web/components/TicketList.jsx`, remplacer la balise ouvrante `<li …>` (lignes 9-16) par :

```jsx
        <li
          key={ticket.id}
          role="button"
          tabIndex={0}
          aria-current={ticket.id === selectedId ? 'true' : undefined}
          className={[
            ticket.status === 'closed' ? 'closed' : '',
            ticket.id === selectedId ? 'selected' : '',
          ].join(' ')}
          onClick={() => onSelect(ticket.id)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onSelect(ticket.id);
            }
          }}
        >
```

Dans `src/web/styles.css`, ajouter après la ligne `.tickets li:hover, .tickets li.selected { … }` :

```css
.tickets li:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
```

- [ ] **Étape 4 : détail conservé**

Dans `src/web/components/TicketDetail.jsx`, remplacer le corps du `try` de `changeStatus` par :

```jsx
      const updated = await api.updateTicket(ticket.id, { status });
      setError(null);
      onUpdated(updated);
```

Dans `src/web/App.jsx` :
- remplacer `const [selectedId, setSelectedId] = useState(null);` par `const [selected, setSelected] = useState(null);` ;
- remplacer la ligne `const selected = tickets.find((t) => t.id === selectedId) ?? null;` par :

```jsx
  // Le détail reste affiché même si le ticket sort du filtre courant (par exemple clos sous « Ouverts »).
  const select = (id) => setSelected(tickets.find((t) => t.id === id) ?? null);
  const handleUpdated = (ticket) => {
    setSelected(ticket);
    refresh();
  };
```

- remplacer `<TicketList tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />` par
  `<TicketList tickets={tickets} selectedId={selected?.id ?? null} onSelect={select} />` ;
- remplacer `<TicketDetail ticket={selected} onUpdated={refresh} />` par
  `<TicketDetail key={selected.id} ticket={selected} onUpdated={handleUpdated} />`.
  La `key` remet à zéro le message d'erreur local quand on change de ticket.

- [ ] **Étape 5 : vérifier**

Run: `npm test && npm run lint`
Expected : tout PASS (le plugin `react-hooks` ne signale rien).

Vérification manuelle : `npm run dev`, ouvrir http://localhost:5173. Naviguer dans la liste avec
Tab puis Entrée, et vérifier que le détail s'ouvre. Passer un ticket à « Clos » sous « Ouverts » :
il quitte la liste mais son détail reste affiché. Les stats de l'en-tête ont une somme égale au total.

- [ ] **Étape 6 : commit**

```bash
git add src/web tests/web
git commit -m "fix(web): liste utilisable au clavier, détail conservé après changement de statut"
```

---

## Clôture

- [ ] `npm test`, `npm run lint`, `npm run build` : tous verts sous Node 22.
- [ ] `npm run db:reset` puis `npm start` : 18 tickets importés, stats cohérentes, notifications
  visibles dans `npm run notif:mock` (avec le `.env` issu de `.env.example`).
- [ ] Rappeler à l'utilisateur les actions manuelles de la tâche 1 (révocation de la clé,
  décision sur la réécriture de l'historique) et la décision de push / PR de la branche `fix/analyse-argos`.
