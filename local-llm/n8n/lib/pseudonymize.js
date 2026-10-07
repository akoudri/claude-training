// Pseudonymisation déterministe des textes qui quittent la machine.
// Ce fichier est testé avec `node --test` et embarqué tel quel dans les nœuds Code de n8n
// (voir n8n/src/builder.mjs, libCode).

const WORD_CHAR = /[\p{L}\p{N}]/u;

function normalize(text) {
  return String(text)
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .toLowerCase()
    .replace(/[\s\u002D\u2010-\u2015\u2212]/gu, ' ')
    .replace(/['\u2018\u2019\u02BC\u0060\u00B4]/gu, "'");
}

function skeleton(text) {
  return normalize(text).replace(/[^\p{L}\p{N}]+/gu, '');
}

// Texte normalisé, et pour chaque caractère normalisé sa position dans le texte d'origine.
function buildIndex(text) {
  let norm = '';
  const map = [];
  let pos = 0;
  for (const char of Array.from(text)) {
    const n = normalize(char);
    for (let k = 0; k < n.length; k++) map.push(pos);
    norm += n;
    pos += char.length;
  }
  map.push(pos);
  return { norm, map };
}

function findOccurrences(text, term, wholeWord) {
  const source = String(text ?? '');
  const needle = normalize(term ?? '').trim();
  if (!needle) return [];
  const { norm, map } = buildIndex(source);
  const found = [];
  let from = 0;
  for (;;) {
    const start = norm.indexOf(needle, from);
    if (start === -1) break;
    const end = start + needle.length;
    const before = start === 0 || !WORD_CHAR.test(norm[start - 1]);
    const after = end === norm.length || !WORD_CHAR.test(norm[end]);
    if (!wholeWord || (before && after)) found.push([map[start], map[end]]);
    from = start + 1;
  }
  return found;
}

function maskContacts(text) {
  return String(text)
    .replace(/\bhttps?:\/\/[^\s)>\]]+|\bwww\.[^\s)>\]]+/gi, '[URL]')
    .replace(/[\p{L}\p{N}._%+-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+/gu, '[EMAIL]');
}

function loadTerms(raw) {
  let data = raw;
  if (typeof raw === 'string') {
    try {
      data = JSON.parse(raw);
    } catch {
      return { ok: false, termes: [], erreur: 'dictionnaire illisible' };
    }
  }
  if (!data || !Array.isArray(data.termes)) return { ok: false, termes: [], erreur: 'dictionnaire indisponible' };
  if (data.termes.length === 0) return { ok: false, termes: [], erreur: 'dictionnaire vide' };
  // Une entrée mal formée invalide tout le dictionnaire : l'ignorer laisserait passer un terme.
  const valide = (t) => t && typeof t.terme === 'string' && normalize(t.terme).trim() && typeof t.remplacement === 'string';
  if (!data.termes.every(valide)) return { ok: false, termes: [], erreur: 'dictionnaire invalide' };
  return { ok: true, termes: data.termes, erreur: null };
}

function pseudonymize(text, termes) {
  // Contacts masqués d'abord : sinon un terme remplacé dans « x@novaltis.example »
  // casserait l'adresse et elle ne serait plus reconnue.
  const source = maskContacts(String(text ?? ''));
  const ordered = [...termes].sort((a, b) => normalize(b.terme).trim().length - normalize(a.terme).trim().length);
  // Un seul passage sur le texte d'origine : un remplacement n'est jamais retraité.
  const taken = [];
  for (const t of ordered) {
    for (const [start, end] of findOccurrences(source, t.terme, true)) {
      if (taken.some(([s, e]) => start < e && s < end)) continue;
      taken.push([start, end, t.remplacement]);
    }
  }
  taken.sort((a, b) => a[0] - b[0]);
  let out = '';
  let last = 0;
  for (const [start, end, remplacement] of taken) {
    out += source.slice(last, start) + remplacement;
    last = end;
  }
  return out + source.slice(last);
}

// Contrôle strict : avec squelettes (lettres et chiffres uniquement), pour attraper « AcmeCorp », « Acme-Défense », « Acme  Défense ».
function countResidual(text, termes) {
  const textSkeleton = skeleton(text);
  let count = 0;
  for (const t of termes) {
    const termSkeleton = skeleton(t.terme);
    if (!termSkeleton) continue; // skip empty skeletons
    let from = 0;
    for (;;) {
      const idx = textSkeleton.indexOf(termSkeleton, from);
      if (idx === -1) break;
      count += 1;
      from = idx + 1; // allow overlapping
    }
  }
  return count;
}

if (typeof module !== 'undefined') {
  module.exports = { normalize, findOccurrences, maskContacts, loadTerms, pseudonymize, countResidual, skeleton };
}
