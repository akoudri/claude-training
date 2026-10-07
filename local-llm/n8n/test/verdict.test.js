const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizeVerdict, errorVerdict, orderChunks, checkReferentielLength, MAX_REFERENTIEL_CHARS } = require('../lib/verdict');

const DOC = 'Proposition – Projet Héron, v2.md';

test('un verdict valide est conservé, citations nettoyées et tronquées', () => {
  const v = normalizeVerdict({ statut: 'couverte', justification: ' OK ', citations: [{ source: DOC, extrait: ` ${'a'.repeat(400)} ` }, { source: 1 }] }, DOC);
  assert.equal(v.statut, 'couverte');
  assert.equal(v.justification, 'OK');
  assert.equal(v.citations.length, 1);
  assert.equal(v.citations[0].extrait.length, 300);
});

test('« couverte » sans citation du document analysé devient « indeterminee »', () => {
  const v = normalizeVerdict({ statut: 'couverte', justification: 'Vu', citations: [{ source: 'sow-exemple.md', extrait: 'x' }] }, DOC);
  assert.equal(v.statut, 'indeterminee');
  assert.match(v.justification, /^Verdict « couverte » rejeté : aucune citation du document analysé\./);
});

test('la source est comparée sans casse ni chemin', () => {
  const v = normalizeVerdict({ statut: 'couverte', justification: 'Vu', citations: [{ source: `/data/documents/${DOC.toUpperCase()}`, extrait: 'x' }] }, DOC);
  assert.equal(v.statut, 'couverte');
});

test('la source est comparée sans variante de normalisation (NFC/NFD)', () => {
  const v = normalizeVerdict({ statut: 'couverte', justification: 'Vu', citations: [{ source: DOC.normalize('NFD'), extrait: 'x' }] }, DOC);
  assert.equal(v.statut, 'couverte');
});

test('statut invalide ou sortie absente', () => {
  assert.equal(normalizeVerdict({ statut: 'oui', justification: 'x', citations: [] }, DOC).statut, 'indeterminee');
  assert.match(normalizeVerdict({ statut: 'oui', justification: 'x', citations: [] }, DOC).justification, /^Statut invalide/);
  assert.equal(normalizeVerdict(null, DOC).statut, 'indeterminee');
});

test('errorVerdict distingue les itérations épuisées', () => {
  assert.equal(errorVerdict('Agent stopped due to max iterations.').justification, 'Recherche non concluante.');
  assert.equal(errorVerdict('Failed to parse').justification, "Erreur d'analyse.");
});

test('orderChunks trie selon la position, extraits sans position à la fin', () => {
  const rows = [
    { text: 'C', metadata: {} },
    { text: 'B', metadata: { loc: { lines: { from: 20 } } } },
    { text: 'A', metadata: { loc: { lines: { from: 1 } } } },
  ];
  assert.equal(orderChunks(rows), 'A\n\nB\n\nC');
});

test('checkReferentielLength refuse un référentiel trop long', () => {
  assert.doesNotThrow(() => checkReferentielLength('a'.repeat(MAX_REFERENTIEL_CHARS)));
  assert.throws(() => checkReferentielLength('a'.repeat(MAX_REFERENTIEL_CHARS + 1)), /trop long/);
});
