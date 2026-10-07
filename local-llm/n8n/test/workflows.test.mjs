import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { CREDS, IDS } from '../src/constants.mjs';

const DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'src', 'workflows');
const modules = readdirSync(DIR).filter((f) => f.endsWith('.mjs')).sort();

test('au moins un workflow est défini', () => assert.ok(modules.length > 0));

for (const file of modules) {
  test(`structure de ${file}`, async () => {
    const { default: build } = await import(pathToFileURL(path.join(DIR, file)));
    const json = build().toJSON({ credentialIds: Object.fromEntries(Object.values(CREDS).map((n, i) => [n, `cred${i}`])) });
    assert.match(json.id, /^[A-Za-z0-9]{16}$/);
    assert.ok(Object.values(IDS).includes(json.id), 'identifiant déclaré dans IDS');
    const names = new Set(json.nodes.map((n) => n.name));
    assert.equal(names.size, json.nodes.length, 'noms de nœuds uniques');
    for (const [from, byType] of Object.entries(json.connections)) {
      assert.ok(names.has(from), `source inconnue : ${from}`);
      for (const outputs of Object.values(byType)) for (const out of outputs) for (const c of out) assert.ok(names.has(c.node), `cible inconnue : ${c.node}`);
    }
    for (const n of json.nodes) {
      for (const cred of Object.values(n.credentials ?? {})) {
        assert.ok(Object.values(CREDS).includes(cred.name), `identifiant inconnu : ${cred.name}`);
        assert.ok(cred.id, 'identifiant résolu');
      }
      if (n.type === 'n8n-nodes-base.formTrigger' || n.type === 'n8n-nodes-base.webhook') {
        // Sans webhookId, n8n 2.x n'enregistre pas le chemin (« No webhook path could be found »).
        assert.match(n.webhookId ?? '', /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/, `webhookId manquant : ${n.name}`);
      }
      if (n.type === 'n8n-nodes-base.formTrigger' && n.typeVersion >= 2.2) {
        // Depuis la v2.2, le chemin et le texte de confirmation sont des options ; ailleurs, n8n les ignore.
        assert.equal(n.parameters.path, undefined, 'chemin du formulaire dans options.path');
        assert.match(n.parameters.options?.path ?? '', /^[a-z0-9-]+$/, 'options.path renseigné');
        assert.equal(n.parameters.options?.formSubmittedText, undefined, 'texte de confirmation dans options.respondWithOptions');
      }
      if (n.type === '@n8n/n8n-nodes-langchain.lmChatOllama') {
        assert.equal(n.parameters.options.think, false, 'réflexion désactivée');
        assert.equal(n.parameters.options.numCtx, undefined, 'numCtx non fixé');
      }
    }
    if (json.id !== IDS.alerte && !json.id.startsWith('cnfTest')) assert.equal(json.settings.errorWorkflow, IDS.alerte);
  });
}
