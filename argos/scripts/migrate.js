import { openDb, migrate } from '../src/api/db.js';

const applied = migrate(openDb());
console.log(applied.length ? `Migrations appliquées : ${applied.join(', ')}` : 'Base à jour.');
