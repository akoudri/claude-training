import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { setup } from '../helpers.js';

describe('GET /api/tickets', () => {
  it('renvoie tous les tickets par défaut', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(4);
  });

  it('status=open ne renvoie que les tickets non clos', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets?status=open');
    expect(res.body.map((t) => t.title)).toEqual(['Ticket ouvert', 'Ticket en cours']);
  });

  it('status=closed renvoie tous les tickets clos, y compris ceux importés', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets?status=closed');
    expect(res.body.map((t) => t.title)).toEqual([
      'Ticket clos',
      "Ticket clos importé de l'ancien outil",
    ]);
  });

  it('renvoie tous les tickets pour un filtre inconnu', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets?status=constructor');
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(4);
  });
});

describe('GET /api/tickets/:id', () => {
  it('renvoie le ticket demandé', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets/1');
    expect(res.status).toBe(200);
    expect(res.body.title).toBe('Ticket ouvert');
  });

  it('renvoie 404 pour un ticket inexistant', async () => {
    const { app } = setup();
    const res = await request(app).get('/api/tickets/999');
    expect(res.status).toBe(404);
  });
});

describe('POST /api/tickets', () => {
  it('crée un ticket ouvert et notifie sa création', async () => {
    const { app, notifier } = setup({ fixture: null });
    const res = await request(app)
      .post('/api/tickets')
      .send({ title: 'Nouveau', description: 'Détail', priority: 'high' });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ title: 'Nouveau', status: 'open', priority: 'high' });
    expect(notifier.events).toEqual([
      { event: 'ticket.created', payload: { id: res.body.id, title: 'Nouveau' } },
    ]);
  });

  it('refuse un ticket sans titre', async () => {
    const { app } = setup({ fixture: null });
    const res = await request(app).post('/api/tickets').send({ title: '  ' });
    expect(res.status).toBe(400);
  });

  it('refuse une priorité inconnue', async () => {
    const { app } = setup({ fixture: null });
    const res = await request(app).post('/api/tickets').send({ title: 'x', priority: 'urgent' });
    expect(res.status).toBe(400);
  });
});

describe('PATCH /api/tickets/:id', () => {
  it('change le statut et notifie le changement', async () => {
    const { app, notifier } = setup();
    const res = await request(app).patch('/api/tickets/1').send({ status: 'closed' });
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('closed');
    expect(notifier.events).toEqual([
      { event: 'ticket.status_changed', payload: { id: 1, from: 'open', to: 'closed' } },
    ]);
  });

  it('refuse un statut hors de la liste autorisée', async () => {
    const { app } = setup();
    const res = await request(app).patch('/api/tickets/1').send({ status: 'Closed' });
    expect(res.status).toBe(400);
  });

  it("ne notifie pas si le statut n'a pas changé", async () => {
    const { app, notifier } = setup();
    await request(app).patch('/api/tickets/1').send({ assignee: 'camille' });
    expect(notifier.events).toEqual([]);
  });
});

describe('validation des champs', () => {
  it.each([
    ['une description non textuelle', { title: 'x', description: { a: 1 } }],
    ['un responsable non textuel', { title: 'x', assignee: ['camille'] }],
    ['un titre trop long', { title: 'x'.repeat(201) }],
    ['une description trop longue', { title: 'x', description: 'x'.repeat(5001) }],
  ])('POST refuse %s avec 400', async (_label, body) => {
    const { app } = setup({ fixture: null });
    const res = await request(app).post('/api/tickets').send(body);
    expect(res.status).toBe(400);
    expect(res.body.error).toBeTruthy();
  });

  it('PATCH accepte de retirer le responsable', async () => {
    const { app } = setup();
    await request(app).patch('/api/tickets/1').send({ assignee: 'camille' });
    const res = await request(app).patch('/api/tickets/1').send({ assignee: null });
    expect(res.status).toBe(200);
    expect(res.body.assignee).toBeNull();
  });

  it('PATCH retire les espaces autour du titre', async () => {
    const { app } = setup();
    const res = await request(app).patch('/api/tickets/1').send({ title: '  Nouveau titre  ' });
    expect(res.body.title).toBe('Nouveau titre');
  });

  it('nomme le champ trop long en français', async () => {
    const { app } = setup({ fixture: null });
    const res = await request(app).post('/api/tickets').send({ title: 'x'.repeat(201) });
    expect(res.body.error).toBe('Le champ titre dépasse 200 caractères');
  });
});
