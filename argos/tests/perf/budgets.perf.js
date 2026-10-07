import { describe, it, expect, beforeAll } from 'vitest';
import request from 'supertest';
import { openDb, migrate } from '../../src/api/db.js';
import { importTickets } from '../../src/api/import.js';
import * as tickets from '../../src/api/repositories/tickets.js';
import { makeRecords, setupWithTickets } from './seed.js';
import { median } from './measure.js';

// Budgets volontairement larges (environ 10 fois la durée mesurée sur un poste de développement) :
// ils détectent une régression d'ordre de grandeur (requête N+1, boucle quadratique),
// pas une variation de quelques pour cent. Pour mesurer finement : npm run bench.
const N = 10_000;

describe(`performances avec ${N} tickets`, () => {
  let ctx;
  beforeAll(() => {
    ctx = setupWithTickets(N);
  });

  it('findAll renvoie toute la liste en moins de 100 ms', async () => {
    expect(await median(() => tickets.findAll(ctx.db))).toBeLessThan(100);
  });

  it('findAll filtré sur les tickets non clos en moins de 100 ms', async () => {
    expect(await median(() => tickets.findAll(ctx.db, { status: 'open' }))).toBeLessThan(100);
  });

  it('countByStatus calcule les statistiques en moins de 20 ms', async () => {
    expect(await median(() => tickets.countByStatus(ctx.db))).toBeLessThan(20);
  });

  it('findById répond en moins de 1 ms', async () => {
    expect(await median(() => tickets.findById(ctx.db, N / 2), { runs: 101 })).toBeLessThan(1);
  });

  it('GET /api/tickets sérialise toute la liste en moins de 300 ms', async () => {
    const ms = await median(async () => {
      const res = await request(ctx.app).get('/api/tickets');
      expect(res.body).toHaveLength(N);
    });
    expect(ms).toBeLessThan(300);
  });

  it('GET /api/stats répond en moins de 50 ms', async () => {
    expect(await median(() => request(ctx.app).get('/api/stats'))).toBeLessThan(50);
  });
});

describe('performances en écriture', () => {
  it('crée 1 000 tickets par POST /api/tickets en moins de 3 s', async () => {
    const { app, notifier } = setupWithTickets(0);
    const start = performance.now();
    for (let i = 0; i < 1000; i++) {
      await request(app).post('/api/tickets').send({ title: `Ticket ${i}` });
    }
    expect(performance.now() - start).toBeLessThan(3000);
    expect(notifier.events).toHaveLength(1000);
  });

  it('change le statut de 1 000 tickets par PATCH en moins de 3 s', async () => {
    const { app } = setupWithTickets(1000);
    const start = performance.now();
    for (let id = 1; id <= 1000; id++) {
      await request(app).patch(`/api/tickets/${id}`).send({ status: 'closed' });
    }
    expect(performance.now() - start).toBeLessThan(3000);
  });

  it(`importe un historique de ${N} tickets en moins de 500 ms`, async () => {
    const records = makeRecords(N);
    const ms = await median(
      () => {
        const db = openDb(':memory:');
        migrate(db);
        importTickets(db, records);
        db.close();
      },
      { warmup: 1, runs: 3 },
    );
    expect(ms).toBeLessThan(500);
  });
});
