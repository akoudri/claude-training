#!/usr/bin/env node
// Compare un rapport de conformité à la vérité terrain du corpus d'exemple.
// Usage : node n8n/scripts/evaluate-report.mjs reports/conformite-….md [n8n/exemples/verite-terrain.json]
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const STATUT = '(couverte|partielle|non_couverte|indeterminee)';

export function canonId(id) {
  return String(id).toUpperCase().replace(/[^A-Z0-9]/g, '').replace(/([A-Z])0+(\d)/g, '$1$2');
}

export function parseReport(markdown) {
  const statuts = new Map();
  const citations = new Map();
  let courant = null;
  for (const ligne of markdown.split('\n')) {
    const row = ligne.match(new RegExp(`^\\| (.+?) \\| .+? \\| .+? \\| ${STATUT} \\|`));
    if (row) statuts.set(canonId(row[1]), row[2]);
    const titre = ligne.match(/^### (.+?) — /);
    if (titre) {
      courant = canonId(titre[1]);
      citations.set(courant, []);
    }
    const cite = ligne.match(/^- \[(.+?)\] « /);
    if (cite && courant) citations.get(courant).push(cite[1]);
  }
  return { statuts, citations };
}

export function evaluate(markdown, verite) {
  const { statuts, citations } = parseReport(markdown);
  const manquantes = verite.exigences.filter((e) => !statuts.has(canonId(e.id))).map((e) => e.id);
  const justes = verite.exigences.filter((e) => statuts.get(canonId(e.id)) === e.statut).length;
  const omissionsDetectees = verite.omissions.filter((id) => statuts.get(canonId(id)) === 'non_couverte');
  const couvertesSansCitation = [...statuts]
    .filter(([id, s]) => s === 'couverte' && !(citations.get(id) ?? []).includes(verite.documentAnalyse))
    .map(([id]) => verite.exigences.find((e) => canonId(e.id) === id)?.id ?? id);
  const total = verite.exigences.length;
  const ok = manquantes.length === 0 && justes / total >= 0.8
    && omissionsDetectees.length === verite.omissions.length && couvertesSansCitation.length === 0;
  return { manquantes, justes, total, omissionsDetectees, couvertesSansCitation, ok };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [rapport, veritePath = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'exemples', 'verite-terrain.json')] = process.argv.slice(2);
  const resultat = evaluate(readFileSync(rapport, 'utf8'), JSON.parse(readFileSync(veritePath, 'utf8')));
  console.log(JSON.stringify(resultat, null, 2));
  process.exit(resultat.ok ? 0 : 1);
}
