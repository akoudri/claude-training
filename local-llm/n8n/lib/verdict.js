// Contrôle des verdicts produits par l'agent et préparation du document référentiel.

const STATUTS_VALIDES = ['couverte', 'partielle', 'non_couverte', 'indeterminee'];
// ~20 000 tokens : laisse de la place au prompt et à la réponse dans un contexte de 32k.
const MAX_REFERENTIEL_CHARS = 80000;

function baseName(source) {
  return String(source).split(/[\\/]/).pop().trim().toLowerCase().normalize('NFC');
}

function normalizeVerdict(raw, documentAnalyse) {
  const v = raw && typeof raw === 'object' ? raw : {};
  const citations = (Array.isArray(v.citations) ? v.citations : [])
    .filter((c) => c && typeof c.source === 'string' && typeof c.extrait === 'string' && c.extrait.trim())
    .map((c) => ({ source: c.source.trim(), extrait: c.extrait.trim().slice(0, 300) }));
  let justification = typeof v.justification === 'string' && v.justification.trim() ? v.justification.trim() : 'Pas de justification fournie.';
  let statut = v.statut;
  if (!STATUTS_VALIDES.includes(statut)) {
    justification = `Statut invalide (« ${statut} »). ${justification}`;
    statut = 'indeterminee';
  }
  // Règle de la spec : « couverte » exige une citation du document analysé.
  if (statut === 'couverte' && !citations.some((c) => baseName(c.source) === baseName(documentAnalyse))) {
    statut = 'indeterminee';
    justification = `Verdict « couverte » rejeté : aucune citation du document analysé. ${justification}`;
  }
  return { statut, justification, citations };
}

function errorVerdict(message) {
  const justification = /max(imum)? iterations/i.test(String(message ?? '')) ? 'Recherche non concluante.' : "Erreur d'analyse.";
  return { statut: 'indeterminee', justification, citations: [] };
}

function orderChunks(rows) {
  const position = (r) => {
    const from = r?.metadata?.loc?.lines?.from;
    return Number.isFinite(from) ? from : Number.POSITIVE_INFINITY;
  };
  return rows
    .map((r, i) => ({ r, i }))
    .sort((a, b) => position(a.r) - position(b.r) || a.i - b.i)
    .map(({ r }) => r.text)
    .join('\n\n');
}

function checkReferentielLength(texte) {
  if (texte.length > MAX_REFERENTIEL_CHARS) {
    throw new Error(`Document référentiel trop long (${texte.length} caractères, maximum ${MAX_REFERENTIEL_CHARS}).`);
  }
}

if (typeof module !== 'undefined') {
  module.exports = { normalizeVerdict, errorVerdict, orderChunks, checkReferentielLength, MAX_REFERENTIEL_CHARS };
}
