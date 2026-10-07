import { describe, it, expect } from 'vitest';
import request from 'supertest';
import { setup } from '../helpers.js';
import * as tickets from '../../src/api/repositories/tickets.js';

function setupWith(records) {
  const ctx = setup({ fixture: null });
  for (const record of records) tickets.create(ctx.db, record);
  return ctx;
}

const search = (app, query) => request(app).get('/api/tickets').query(query);
const titles = (res) => res.body.map((t) => t.title);

describe('GET /api/tickets?q= (recherche)', () => {
  it('trouve un ticket par son titre', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }, { title: 'Accès VPN' }]);
    const res = await search(app, { q: 'imprimante' });
    expect(res.status).toBe(200);
    expect(titles(res)).toEqual(['Panne imprimante']);
  });

  it('trouve un ticket par sa description', async () => {
    const { app } = setupWith([
      { title: 'Panne', description: "L'imprimante du 2e étage bourre" },
      { title: 'Accès VPN', description: 'Mot de passe expiré' },
    ]);
    const res = await search(app, { q: 'bourre' });
    expect(titles(res)).toEqual(['Panne']);
  });

  it('renvoie 200 et une liste vide quand aucun ticket ne correspond', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }]);
    const res = await search(app, { q: 'introuvable' });
    expect(res.status).toBe(200);
    expect(res.body).toEqual([]);
  });

  // LIKE ignore déjà la casse en ASCII : le cas utile est celui des lettres accentuées.
  it('est insensible à la casse, y compris pour les lettres accentuées', async () => {
    const { app } = setupWith([{ title: 'Fuite au 2e étage' }, { title: 'Accès VPN' }]);
    const res = await search(app, { q: 'ÉTAGE' });
    expect(titles(res)).toEqual(['Fuite au 2e étage']);
  });

  it('est insensible aux accents : « echec » trouve « Échec »', async () => {
    const { app } = setupWith([{ title: 'Échec de la sauvegarde' }, { title: 'Accès VPN' }]);
    const res = await search(app, { q: 'echec' });
    expect(titles(res)).toEqual(['Échec de la sauvegarde']);
  });

  it('est insensible aux accents : « accés » trouve « Accès »', async () => {
    const { app } = setupWith([{ title: 'Échec de la sauvegarde' }, { title: 'Accès VPN' }]);
    const res = await search(app, { q: 'accés' });
    expect(titles(res)).toEqual(['Accès VPN']);
  });

  it('se combine avec le filtre de statut', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }, { title: 'Panne réseau' }, { title: 'Accès VPN' }]);
    await request(app).patch('/api/tickets/2').send({ status: 'closed' });
    const res = await search(app, { q: 'panne', status: 'open' });
    expect(titles(res)).toEqual(['Panne imprimante']);
  });

  it('ignore un mot-clé vide ou fait d’espaces', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }, { title: 'Accès VPN' }]);
    for (const q of ['', '   ']) {
      const res = await search(app, { q });
      expect(titles(res), `q = « ${q} »`).toEqual(['Panne imprimante', 'Accès VPN']);
    }
  });

  it('ignore les espaces autour du mot-clé', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }, { title: 'Accès VPN' }]);
    const res = await search(app, { q: '  vpn ' });
    expect(titles(res)).toEqual(['Accès VPN']);
  });

  it('refuse un mot-clé répété (?q=a&q=b) avec un 400', async () => {
    const { app } = setupWith([{ title: 'Panne imprimante' }]);
    const res = await request(app).get('/api/tickets?q=panne&q=vpn');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Le mot-clé de recherche doit être un texte');
  });

  it('cherche « % » et « _ » littéralement, pas comme jokers', async () => {
    const { app } = setupWith([
      { title: 'Disque plein à 100%' },
      { title: 'Variable NOTIF_API_KEY absente' },
      { title: 'Accès VPN' },
    ]);
    expect(titles(await search(app, { q: '%' }))).toEqual(['Disque plein à 100%']);
    expect(titles(await search(app, { q: '_' }))).toEqual(['Variable NOTIF_API_KEY absente']);
  });

  it('ne fait pas correspondre un mot-clé à cheval sur le titre et la description', async () => {
    const { app } = setupWith([{ title: 'Panne', description: 'imprimante du 2e étage' }]);
    const res = await search(app, { q: 'panne imprimante' });
    expect(res.body).toEqual([]);
  });
});
