#!/usr/bin/env node
// Génère les JSON importables dans n8n à partir de n8n/src/workflows/*.mjs.
// Sans --credentials : JSON versionnables, sans identifiant d'instance.
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';
import { CREDS } from '../src/constants.mjs';

const N8N_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const { values } = parseArgs({
  options: { credentials: { type: 'string' }, out: { type: 'string', default: path.join(N8N_DIR, 'workflows') } },
});

let credentialIds = null;
if (values.credentials) {
  credentialIds = JSON.parse(readFileSync(values.credentials, 'utf8'));
  const missing = Object.values(CREDS).filter((name) => !credentialIds[name]);
  if (missing.length) {
    console.error(`Identifiants à créer dans n8n avant le déploiement : ${missing.join(', ')}`);
    process.exit(1);
  }
}

const dir = path.join(N8N_DIR, 'src', 'workflows');
mkdirSync(values.out, { recursive: true });
for (const file of readdirSync(dir).filter((f) => f.endsWith('.mjs')).sort()) {
  const { default: build } = await import(pathToFileURL(path.join(dir, file)));
  const wf = build();
  const target = path.join(values.out, file.replace(/\.mjs$/, '.json'));
  writeFileSync(target, `${JSON.stringify(wf.toJSON({ credentialIds }), null, 2)}\n`);
  console.log(`${wf.name} → ${target}`);
}
