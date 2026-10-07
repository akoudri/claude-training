import test from 'node:test';
import assert from 'node:assert/strict';
import { canonId, evaluate, parseReport } from '../scripts/evaluate-report.mjs';

const DOC = 'Proposition – Projet Héron, v2.md';
const RAPPORT = `## Tableau de conformité

| ID | Type | Intitulé | Statut | Justification |
|---|---|---|---|---|
| EX-1 | livrable | Inventaire | couverte | ok |
| EX-02 | exigence | Support | non_couverte | absent |
| EX-03 | exigence | Formation | couverte | ok |

## Citations

### EX-1 — Inventaire

- [${DOC}] « D1 »

### EX-02 — Support

_Aucune citation._

### EX-03 — Formation

- [sow-exemple.md] « deux jours »
`;
const VERITE = {
  documentAnalyse: DOC,
  exigences: [{ id: 'EX-01', statut: 'couverte' }, { id: 'EX-02', statut: 'non_couverte' }, { id: 'EX-03', statut: 'partielle' }, { id: 'EX-04', statut: 'couverte' }],
  omissions: ['EX-02'],
};

test('canonId ignore la casse, la ponctuation et les zéros initiaux', () => {
  assert.equal(canonId('ex-01'), canonId('EX 1'));
});

test('parseReport lit statuts et citations', () => {
  const r = parseReport(RAPPORT);
  assert.equal(r.statuts.get(canonId('EX-02')), 'non_couverte');
  assert.deepEqual(r.citations.get(canonId('EX-01')), [DOC]);
});

test('evaluate mesure extraction, justesse, omissions et citations', () => {
  const e = evaluate(RAPPORT, VERITE);
  assert.deepEqual(e.manquantes, ['EX-04']);
  assert.equal(e.justes, 2);
  assert.equal(e.total, 4);
  assert.deepEqual(e.omissionsDetectees, ['EX-02']);
  assert.deepEqual(e.couvertesSansCitation, ['EX-03']);
  assert.equal(e.ok, false);
});
