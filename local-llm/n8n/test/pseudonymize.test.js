const test = require('node:test');
const assert = require('node:assert/strict');
const { normalize, findOccurrences, maskContacts, loadTerms, pseudonymize, countResidual } = require('../lib/pseudonymize');

const TERMES = [
  { terme: 'Acme', remplacement: '[CLIENT-COURT]' },
  { terme: 'Acme Défense', remplacement: '[CLIENT]' },
  { terme: 'Novaltis', remplacement: '[PRESTATAIRE]' },
];

test('normalize retire les accents et la casse', () => {
  assert.equal(normalize('Défense ÉLÉMENT'), 'defense element');
});

test('findOccurrences renvoie les positions dans le texte d\u2019origine', () => {
  assert.deepEqual(findOccurrences('Contrat ACME défense signé', 'Acme Défense', true), [[8, 20]]);
});

test('pseudonymize ignore casse et accents', () => {
  assert.equal(pseudonymize('Contrat ACME defense signé', TERMES), 'Contrat [CLIENT] signé');
});

test('pseudonymize traite les termes les plus longs en premier', () => {
  assert.equal(pseudonymize('Acme Défense et Acme', TERMES), '[CLIENT] et [CLIENT-COURT]');
});

test('pseudonymize respecte les limites de mots', () => {
  assert.equal(pseudonymize('Intégration AcmeCorp', TERMES), 'Intégration AcmeCorp');
});

test('pseudonymize ne retraite pas les remplacements', () => {
  const termes = [{ terme: 'Acme', remplacement: '[CLIENT]' }, { terme: 'client', remplacement: '[ROLE]' }];
  assert.equal(pseudonymize('Acme est le client', termes), '[CLIENT] est le [ROLE]');
});

test('pseudonymize masque mails et URL', () => {
  assert.equal(
    pseudonymize('Contact : jeanne.martin@novaltis.example, voir https://novaltis.example/offre', TERMES),
    'Contact : [EMAIL], voir [URL]',
  );
});

test('maskContacts laisse un texte sans contact intact', () => {
  assert.equal(maskContacts('Livrable D1'), 'Livrable D1');
});

test('countResidual détecte un terme collé à un autre mot', () => {
  assert.equal(countResidual('Intégration AcmeCorp', TERMES), 1);
});

test('countResidual vaut 0 après pseudonymisation d\u2019un texte propre', () => {
  assert.equal(countResidual(pseudonymize('Acme Défense et Novaltis', TERMES), TERMES), 0);
});

test('un remplacement contenant un terme produit un faux résidu (sens sûr)', () => {
  const termes = [{ terme: 'client', remplacement: '[CLIENT]' }];
  assert.equal(countResidual(pseudonymize('le client', termes), termes), 1);
});

test('loadTerms accepte un JSON valide', () => {
  const r = loadTerms('{"termes":[{"terme":"Acme","remplacement":"[C]"}]}');
  assert.equal(r.ok, true);
  assert.equal(r.termes.length, 1);
});

test('loadTerms refuse un JSON illisible, absent, vide ou mal formé', () => {
  assert.deepEqual(loadTerms('{pas du json'), { ok: false, termes: [], erreur: 'dictionnaire illisible' });
  assert.equal(loadTerms(null).erreur, 'dictionnaire indisponible');
  assert.equal(loadTerms({ termes: [] }).erreur, 'dictionnaire vide');
  assert.equal(loadTerms({ termes: [{ terme: 'Acme' }] }).erreur, 'dictionnaire invalide');
  assert.equal(loadTerms({ termes: [{ terme: '  ', remplacement: '[X]' }] }).erreur, 'dictionnaire invalide');
});

// Regression tests for C1: typographic variants
test('pseudonymize remplace Acme Défense avec espace normal', () => {
  const termes = [{ terme: 'Acme Défense', remplacement: '[CLIENT]' }];
  assert.equal(pseudonymize('Acme Défense', termes), '[CLIENT]');
});

test('pseudonymize remplace Acme–Défense avec en dash', () => {
  const termes = [{ terme: 'Acme Défense', remplacement: '[CLIENT]' }];
  assert.equal(pseudonymize('Acme–Défense', termes), '[CLIENT]');
});

test('pseudonymize remplace Acme\nDéfense avec saut de ligne', () => {
  const termes = [{ terme: 'Acme Défense', remplacement: '[CLIENT]' }];
  assert.equal(pseudonymize('Acme\nDéfense', termes), '[CLIENT]');
});

test('pseudonymize remplace L\'Oréal avec apostrophe typographique', () => {
  const termes = [{ terme: 'L\'Oréal', remplacement: '[MARQUE]' }];
  assert.equal(pseudonymize('L\u2019Oréal', termes), '[MARQUE]');
});

test('countResidual détecte double espace dans Acme  Défense', () => {
  const termes = [{ terme: 'Acme Défense', remplacement: '[CLIENT]' }];
  assert.equal(countResidual('Acme  Défense', termes), 1);
});

test('pseudonymize remplace L\'Oréal avec apostrophe gauche U+2018', () => {
  const termes = [{ terme: "L'Oréal", remplacement: '[MARQUE]' }];
  assert.equal(pseudonymize('L\u2018Oréal', termes), '[MARQUE]');
});

test('maskContacts masque élodie.martin@acme.fr entièrement', () => {
  assert.equal(maskContacts('Contact : élodie.martin@acme.fr'), 'Contact : [EMAIL]');
});
