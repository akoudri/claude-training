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
