import { test } from 'vitest';
import request from 'supertest';
import { openDb, migrate } from '../../src/api/db.js';
import { importTickets } from '../../src/api/import.js';
import * as tickets from '../../src/api/repositories/tickets.js';
import { makeRecords, setupWithTickets } from './seed.js';

// Mesures sans seuil (opérations par seconde) : à comparer avant et après une modification.
// Vitest 5 : `bench` est fourni par le contexte du test, `bench.compare` affiche un tableau.
const N = 10_000;
const ctx = setupWithTickets(N);
const records = makeRecords(1000);

test(`dépôt, ${N} tickets`, async ({ bench }) => {
  await bench.compare(
    bench('findAll (tous)', () => tickets.findAll(ctx.db)),
    bench('findAll (non clos)', () => tickets.findAll(ctx.db, { status: 'open' })),
    bench('countByStatus', () => tickets.countByStatus(ctx.db)),
    bench('findById', () => tickets.findById(ctx.db, N / 2)),
  );
});

test(`API HTTP, ${N} tickets`, async ({ bench }) => {
  await bench.compare(
    bench('GET /api/tickets', () => request(ctx.app).get('/api/tickets')),
    bench('GET /api/tickets?status=closed', () => request(ctx.app).get('/api/tickets?status=closed')),
    bench('GET /api/stats', () => request(ctx.app).get('/api/stats')),
    bench('GET /api/tickets/:id', () => request(ctx.app).get(`/api/tickets/${N / 2}`)),
  );
});

test('import de 1 000 tickets dans une base neuve', async ({ bench }) => {
  await bench('importTickets', () => {
    const db = openDb(':memory:');
    migrate(db);
    importTickets(db, records);
    db.close();
  }).run();
});
