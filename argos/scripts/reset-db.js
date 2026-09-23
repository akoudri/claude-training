import { rmSync } from 'node:fs';
import { DEFAULT_DB_FILE, openDb, migrate } from '../src/api/db.js';
import { importFile } from '../src/api/import.js';

rmSync(DEFAULT_DB_FILE, { force: true });
const db = openDb();
console.log(`Migrations appliquées : ${migrate(db).join(', ')}`);
console.log(`Import de l'historique : ${importFile(db, 'data/historique.json')} tickets`);
