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
