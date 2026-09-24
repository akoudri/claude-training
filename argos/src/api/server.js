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
