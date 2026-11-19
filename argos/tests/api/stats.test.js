import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { setup } from '../helpers.js';

describe('GET /api/stats', () => {
  it('compte les tickets créés par statut', async () => {
    const { app } = setup({ fixture: null });
    await request(app).post('/api/tickets').send({ title: 'A' });
    await request(app).post('/api/tickets').send({ title: 'B' });
    await request(app).patch('/api/tickets/2').send({ status: 'in_progress' });

    const res = await request(app).get('/api/stats');
    expect(res.body).toEqual({ total: 2, open: 1, in_progress: 1, closed: 0 });
  });
});
