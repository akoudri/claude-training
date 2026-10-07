import '../src/api/env.js';
import { rmSync } from 'node:fs';
import { DEFAULT_DB_FILE, openDb, migrate } from '../src/api/db.js';
import { importFileOnce } from '../src/api/import.js';
import { HISTORY_FILE } from '../src/api/paths.js';

rmSync(DEFAULT_DB_FILE, { force: true });
const db = openDb();
console.log(`Migrations appliquées : ${migrate(db).join(', ')}`);
console.log(`Import de l'historique : ${importFileOnce(db, HISTORY_FILE)} tickets`);
