import { readFileSync } from 'node:fs';
import { openDb, migrate } from '../src/api/db.js';
import { importTickets } from '../src/api/import.js';
import { createApp } from '../src/api/app.js';

export function loadFixture(name) {
  return JSON.parse(readFileSync(new URL(`./fixtures/${name}`, import.meta.url), 'utf8'));
}

// Notifier de test : enregistre les événements au lieu de les envoyer.
export function fakeNotifier() {
  const events = [];
  return { events, notify: async (event, payload) => events.push({ event, payload }) };
}

export function setup({ fixture = 'historique-extrait.json' } = {}) {
  const db = openDb(':memory:');
  migrate(db);
  if (fixture) importTickets(db, loadFixture(fixture));
  const notifier = fakeNotifier();
  const app = createApp({ db, notifier });
  return { db, app, notifier };
}
