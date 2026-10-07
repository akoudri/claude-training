// Statistiques, rapport Markdown local et composition du mail de synthèse.
// Embarqué dans n8n après pseudonymize.js : les fonctions de ce dernier y sont alors déjà définies.

const libPseudo = typeof pseudonymize === 'function' ? { pseudonymize, countResidual } : require('./pseudonymize');

const STATUTS = ['couverte', 'partielle', 'non_couverte', 'indeterminee'];
const LIBELLES = { couverte: 'Couverte', partielle: 'Partielle', non_couverte: 'Non couverte', indeterminee: 'Indéterminée' };

const MAX_EXIGENCES = 25;
// Longueur max d'un intitulé dans le mail, appliquée APRÈS pseudonymisation : couper avant
// pourrait laisser un fragment de terme sensible que ni le remplacement ni le contrôle ne reconnaissent.
const MAX_INTITULE = 120;

// Motif d'échec : uniquement des comptes, jamais de nom de document (les noms portent des références hors dictionnaire).
function missingDocsMotif(manquants, indexes) {
  return `Document(s) demandé(s) non indexé(s) : ${manquants.length}. Documents indexés : ${indexes.length}. Détail dans l'historique d'exécution n8n.`;
}

// Ligne d'avertissement (nombres seuls) quand la liste d'exigences a été tronquée ; null sinon.
function truncationNote(extraites) {
  return Number(extraites) > MAX_EXIGENCES
    ? `${extraites} exigences extraites, seules les ${MAX_EXIGENCES} premières ont été analysées.`
    : null;
}

function pad(n) {
  return String(n).padStart(2, '0');
}

function formatDateLabel(date) {
  return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function reportFileName(date) {
  return `conformite-${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}.md`;
}

function formatDuration(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)} min ${pad(s % 60)} s`;
}

function computeStats(lignes) {
  const stats = { total: lignes.length, couverte: 0, partielle: 0, non_couverte: 0, indeterminee: 0 };
  for (const l of lignes) stats[STATUTS.includes(l.statut) ? l.statut : 'indeterminee'] += 1;
  return stats;
}

function cell(text) {
  return String(text ?? '').replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ').trim();
}

function buildReport({ referentiel, analyse, debut, fin, lignes, extraites }) {
  const stats = computeStats(lignes);
  const troncature = truncationNote(extraites);
  const out = [
    '# Rapport de conformité',
    '',
    `- **Document référentiel** : ${referentiel}`,
    `- **Document analysé** : ${analyse}`,
    `- **Date** : ${formatDateLabel(fin)}`,
    `- **Durée** : ${formatDuration(fin - debut)}`,
    '',
    ...(troncature ? [`> ⚠️ ${troncature}`, ''] : []),
    '## Synthèse',
    '',
    '| Statut | Nombre |',
    '|---|---|',
    ...STATUTS.map((s) => `| ${LIBELLES[s]} | ${stats[s]} |`),
    `| **Total** | **${stats.total}** |`,
    '',
    '## Tableau de conformité',
    '',
    '| ID | Type | Intitulé | Statut | Justification |',
    '|---|---|---|---|---|',
    ...lignes.map((l) => `| ${cell(l.id)} | ${cell(l.type)} | ${cell(l.intitule)} | ${l.statut} | ${cell(l.justification)} |`),
    '',
    '## Citations',
    '',
  ];
  for (const l of lignes) {
    out.push(`### ${cell(l.id)} — ${cell(l.intitule)}`, '');
    if (l.citations.length === 0) out.push('_Aucune citation._');
    for (const c of l.citations) out.push(`- [${cell(c.source)}] « ${cell(c.extrait)} »`);
    out.push('');
  }
  return out.join('\n');
}

function statsLines(stats, extraites) {
  const troncature = truncationNote(extraites);
  return [`Exigences analysées : ${stats.total}`, ...(troncature ? [troncature] : []), ...STATUTS.map((s) => `- ${LIBELLES[s]} : ${stats[s]}`)];
}

const SIGNATURE = ['', 'Rapport complet : dossier reports/ de la machine locale.'];

function buildMail({ mode, motif, statistiques, lignes = [], dict, dateLabel, extraites }) {
  if (mode === 'echec') {
    let detail = 'motif non communiqué (dictionnaire indisponible).';
    if (dict.ok) {
      const texte = libPseudo.pseudonymize(motif || 'non précisé', dict.termes);
      detail = libPseudo.countResidual(texte, dict.termes) === 0 ? texte : 'motif retiré (occurrences sensibles résiduelles).';
    }
    return {
      subject: `[n8n] Analyse de conformité – ${dateLabel} – échec`,
      text: ["L'analyse de conformité a échoué.", '', `Motif : ${detail}`, ...SIGNATURE].join('\n'),
      detail: 'echec',
    };
  }
  const subject = `[n8n] Analyse de conformité – ${dateLabel} – ${statistiques.couverte}/${statistiques.total} couvertes`;
  const base = ["Résultat de l'analyse de conformité", '', ...statsLines(statistiques, extraites)];
  const reduit = (raison) => ({ subject, text: [...base, '', `Synthèse détaillée retirée : ${raison}.`, ...SIGNATURE].join('\n'), detail: 'statistiques' });
  if (!dict.ok) return reduit(dict.erreur);
  const pseudo = lignes.map((l) => ({
    id: libPseudo.pseudonymize(String(l.id ?? '').replace(/\s+/g, ' ').trim(), dict.termes),
    statut: LIBELLES[l.statut] ?? LIBELLES.indeterminee,
    intitule: libPseudo.pseudonymize(String(l.intitule ?? '').replace(/\s+/g, ' ').trim(), dict.termes),
  }));
  // Contrôle sur les intitulés complets, AVANT la coupure : un terme résiduel coupé en deux
  // échapperait sinon au contrôle.
  const residuel = libPseudo.countResidual(pseudo.map((l) => `${l.id} | ${l.statut} | ${l.intitule}`).join('\n'), dict.termes);
  if (residuel > 0) return reduit(`${residuel} occurrence(s) sensible(s) résiduelle(s)`);
  const tableau = pseudo.map((l) => `${l.id} | ${l.statut} | ${l.intitule.slice(0, MAX_INTITULE)}`);
  return { subject, text: [...base, '', 'ID | Statut | Intitulé', ...tableau, ...SIGNATURE].join('\n'), detail: 'complet' };
}

if (typeof module !== 'undefined') {
  module.exports = { STATUTS, MAX_EXIGENCES, MAX_INTITULE, missingDocsMotif, truncationNote, computeStats, formatDateLabel, reportFileName, buildReport, buildMail };
}
