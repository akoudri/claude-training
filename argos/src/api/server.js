import './env.js';
import { createApp } from './app.js';
import { openDb, migrate } from './db.js';
import { importFile } from './import.js';
import { createNotifier } from './services/notifier.js';

const PORT = Number(process.env.PORT ?? 3000);
const HISTORY_FILE = 'data/historique.json';

const db = openDb();
const applied = migrate(db);
if (applied.length) console.log(`Migrations appliquées : ${applied.join(', ')}`);

// Première exécution : la base est vide, on reprend l'historique de l'ancien outil.
const { n } = db.prepare('SELECT count(*) AS n FROM tickets').get();
if (n === 0) {
  console.log(`Import de l'historique : ${importFile(db, HISTORY_FILE)} tickets`);
}

const app = createApp({ db, notifier: createNotifier(), staticDir: 'dist' });
app.listen(PORT, () => console.log(`Argos API sur http://localhost:${PORT}`));
