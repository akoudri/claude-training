const test = require('node:test');
const assert = require('node:assert/strict');
const { computeStats, formatDateLabel, reportFileName, buildReport, buildMail, missingDocsMotif, MAX_EXIGENCES, MAX_INTITULE } = require('../lib/report');
const { loadTerms } = require('../lib/pseudonymize');

const DICT = loadTerms({ termes: [
  { terme: 'Acme', remplacement: '[CLIENT]' },
  { terme: 'Novaltis', remplacement: '[PRESTATAIRE]' },
] });
const LIGNES = [
  { id: 'EX-01', type: 'livrable', intitule: 'Inventaire pour Acme', statut: 'couverte', justification: 'WP1 | D1', citations: [{ source: 'p.md', extrait: 'Le WP1\nlivre D1' }] },
  { id: 'EX-02', type: 'exigence', intitule: 'Formation Novaltis', statut: 'partielle', justification: '1 jour au lieu de 2', citations: [] },
  { id: 'EX-03', type: 'exigence', intitule: 'Support', statut: 'non_couverte', justification: 'Absent', citations: [] },
];
const STATS = computeStats(LIGNES);
// Instant fixé en UTC : le runner de code de n8n tourne en UTC, les libellés doivent être à l'heure de Paris.
const DATE = new Date('2026-10-05T12:07:00Z');

test('computeStats compte par statut', () => {
  assert.deepEqual(STATS, { total: 3, couverte: 1, partielle: 1, non_couverte: 1, indeterminee: 0 });
});

test('dates et nom de fichier', () => {
  assert.equal(formatDateLabel(DATE), '05/10/2026 14:07');
  assert.equal(reportFileName(DATE), 'conformite-2026-10-05-1407.md');
});

test('buildReport produit en-tête, tableau échappé et citations', () => {
  const md = buildReport({ referentiel: 'sow.md', analyse: 'p.md', debut: new Date(DATE - 125000), fin: DATE, lignes: LIGNES });
  assert.match(md, /- \*\*Durée\*\* : 2 min 05 s/);
  assert.match(md, /\| EX-01 \| livrable \| Inventaire pour Acme \| couverte \| WP1 \\\| D1 \|/);
  assert.match(md, /### EX-01 — Inventaire pour Acme\n\n- \[p\.md\] « Le WP1 livre D1 »/);
  assert.match(md, /### EX-02 — Formation Novaltis\n\n_Aucune citation._/);
  assert.match(md, /\| \*\*Total\*\* \| \*\*3\*\* \|/);
});

test('mail complet : statistiques et intitulés pseudonymisés, sans justification', () => {
  const mail = buildMail({ mode: 'succes', statistiques: STATS, lignes: LIGNES, dict: DICT, dateLabel: '05/10/2026 14:07' });
  assert.equal(mail.detail, 'complet');
  assert.equal(mail.subject, '[n8n] Analyse de conformité – 05/10/2026 14:07 – 1/3 couvertes');
  assert.match(mail.text, /EX-01 \| Couverte \| Inventaire pour \[CLIENT\]/);
  assert.match(mail.text, /EX-02 \| Partielle \| Formation \[PRESTATAIRE\]/);
  assert.doesNotMatch(mail.text, /Acme|Novaltis|WP1|1 jour/);
});

test('mail réduit aux statistiques si un terme subsiste', () => {
  const lignes = [{ ...LIGNES[0], intitule: 'Intégration AcmeCorp' }];
  const mail = buildMail({ mode: 'succes', statistiques: computeStats(lignes), lignes, dict: DICT, dateLabel: 'x' });
  assert.equal(mail.detail, 'statistiques');
  assert.match(mail.text, /Synthèse détaillée retirée : 1 occurrence\(s\) sensible\(s\) résiduelle\(s\)\./);
  assert.doesNotMatch(mail.text, /Acme/);
});

test('mail réduit aux statistiques si le dictionnaire manque', () => {
  const mail = buildMail({ mode: 'succes', statistiques: STATS, lignes: LIGNES, dict: loadTerms(null), dateLabel: 'x' });
  assert.equal(mail.detail, 'statistiques');
  assert.match(mail.text, /Synthèse détaillée retirée : dictionnaire indisponible\./);
  assert.doesNotMatch(mail.text, /Acme|Inventaire/);
});

test('mail d\u2019échec : motif pseudonymisé, ou retiré sans dictionnaire', () => {
  const avec = buildMail({ mode: 'echec', motif: 'Document absent : Offre Novaltis.docx', dict: DICT, dateLabel: 'x' });
  assert.equal(avec.subject, '[n8n] Analyse de conformité – x – échec');
  assert.match(avec.text, /Motif : Document absent : Offre \[PRESTATAIRE\]\.docx/);
  const sans = buildMail({ mode: 'echec', motif: 'Offre Novaltis.docx', dict: loadTerms(null), dateLabel: 'x' });
  assert.doesNotMatch(sans.text, /Novaltis/);
});

// Regression test for C1: typographic variants in buildMail
test('mail complet avec intitulés contenant variantes typographiques', () => {
  const dict = loadTerms({ termes: [
    { terme: 'Acme Défense', remplacement: '[CLIENT]' },
    { terme: "L'Oréal", remplacement: '[MARQUE]' },
  ] });
  const lignes = [
    { id: 'L1', type: 'exigence', intitule: 'Acme Défense', statut: 'couverte', justification: 'x', citations: [{ source: 'p.md', extrait: 'x' }] },
    { id: 'L2', type: 'exigence', intitule: 'Acme–Défense', statut: 'couverte', justification: 'x', citations: [{ source: 'p.md', extrait: 'x' }] },
    { id: 'L3', type: 'exigence', intitule: 'L\u2019Oréal', statut: 'couverte', justification: 'x', citations: [{ source: 'p.md', extrait: 'x' }] },
    { id: 'L4', type: 'exigence', intitule: 'Acme\nDéfense', statut: 'couverte', justification: 'x', citations: [{ source: 'p.md', extrait: 'x' }] },
  ];
  const mail = buildMail({ mode: 'succes', statistiques: computeStats(lignes), lignes, dict, dateLabel: 'x' });
  assert.equal(mail.detail, 'complet');
  assert.match(mail.text, /\[CLIENT\]/);
  assert.match(mail.text, /\[MARQUE\]/);
  assert.doesNotMatch(mail.text, /Acme|Or[eé]al/i);
});

test('mail complet : double espace aplati puis pseudonymisé', () => {
  const dict = loadTerms({ termes: [
    { terme: 'Acme Défense', remplacement: '[CLIENT]' },
  ] });
  const lignes = [
    { id: 'L1', type: 'exigence', intitule: 'Acme  Défense', statut: 'couverte', justification: 'x', citations: [{ source: 'p.md', extrait: 'x' }] },
  ];
  const mail = buildMail({ mode: 'succes', statistiques: computeStats(lignes), lignes, dict, dateLabel: 'x' });
  assert.equal(mail.detail, 'complet');
  assert.match(mail.text, /\[CLIENT\]/);
  assert.doesNotMatch(mail.text, /Acme/);
});

test('motif de documents manquants : comptes seuls, aucun nom de document', () => {
  const motif = missingDocsMotif(['secret-acme.md', 'p.md'], ['sow-novaltis.md', 'autre.md', 'p-x.md']);
  assert.equal(motif, "Document(s) demandé(s) non indexé(s) : 2. Documents indexés : 3. Détail dans l'historique d'exécution n8n.");
  assert.doesNotMatch(motif, /acme|novaltis|\.md/i);
});

test('motif sans aucun document indexé', () => {
  assert.match(missingDocsMotif(['x.md'], []), /: 1\. Documents indexés : 0\./);
});

test('buildReport signale la troncature des exigences', () => {
  const md = buildReport({ referentiel: 'a', analyse: 'b', debut: DATE, fin: DATE, lignes: LIGNES, extraites: 31 });
  assert.match(md, /> ⚠️ 31 exigences extraites, seules les 25 premières ont été analysées\./);
  assert.equal(MAX_EXIGENCES, 25);
  const ok = buildReport({ referentiel: 'a', analyse: 'b', debut: DATE, fin: DATE, lignes: LIGNES, extraites: 25 });
  assert.doesNotMatch(ok, /⚠️/);
});

test('mail : ligne de troncature numérique, statut inconnu en Indéterminée', () => {
  const lignes = [{ id: 'X', intitule: 'Y', statut: 'bizarre' }];
  const mail = buildMail({ mode: 'succes', statistiques: computeStats(lignes), lignes, dict: DICT, dateLabel: 'd', extraites: 40 });
  assert.match(mail.text, /X \| Indéterminée \| Y/);
  assert.doesNotMatch(mail.text, /undefined/);
  assert.match(mail.text, /40 exigences extraites, seules les 25 premières ont été analysées\./);
  const reduit = buildMail({ mode: 'succes', statistiques: computeStats(lignes), lignes, dict: { ok: false, erreur: 'e' }, dateLabel: 'd', extraites: 40 });
  assert.match(reduit.text, /40 exigences extraites/);
});

test('rapport : la source des citations est échappée', () => {
  const l = [{ id: 'A', type: 'exigence', intitule: 'i', statut: 'couverte', justification: 'j', citations: [{ source: 'a]\nb', extrait: 'e' }] }];
  assert.match(buildReport({ referentiel: 'a', analyse: 'b', debut: DATE, fin: DATE, lignes: l }), /- \[a] b\] « e »/);
});

test('buildMail tronque l\'intitulé après pseudonymisation, sans fragment de terme', () => {
  const dict = loadTerms({ termes: [{ terme: 'Novaltis Industries', remplacement: '[PRESTATAIRE]' }] });
  const intitule = `${'x'.repeat(110)} Novaltis Industries ${'y'.repeat(20)}`;
  const mail = buildMail({ mode: 'succes', statistiques: computeStats([{ statut: 'couverte' }]), lignes: [{ id: 'EX-01', statut: 'couverte', intitule }], dict, dateLabel: '05/10/2026 14:07' });
  assert.equal(mail.detail, 'complet');
  assert.doesNotMatch(mail.text, /Novaltis/);
  const ligne = mail.text.split('\n').find((l) => l.startsWith('EX-01'));
  assert.ok(ligne.split(' | ')[2].length <= MAX_INTITULE);
});

test('buildMail contrôle les résidus avant la coupure de l\'intitulé', () => {
  const dict = loadTerms({ termes: [{ terme: 'Novaltis Industries', remplacement: '[PRESTATAIRE]' }] });
  // Variante collée, non remplacée mais détectée par le contrôle, à cheval sur la coupure.
  const intitule = `${'x'.repeat(110)} NovaltisIndustries ${'y'.repeat(20)}`;
  const mail = buildMail({ mode: 'succes', statistiques: computeStats([{ statut: 'couverte' }]), lignes: [{ id: 'EX-01', statut: 'couverte', intitule }], dict, dateLabel: '05/10/2026 14:07' });
  assert.equal(mail.detail, 'statistiques');
  assert.doesNotMatch(mail.text, /Novaltis/);
});
