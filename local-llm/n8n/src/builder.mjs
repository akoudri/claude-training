// Petit constructeur de workflows n8n : décrit les nœuds en JavaScript lisible
// et produit le JSON accepté par `n8n import:workflow`.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const N8N_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Code des bibliothèques testées, à placer en tête d'un nœud Code.
export function libCode(...files) {
  return files.map((f) => readFileSync(path.join(N8N_DIR, 'lib', f), 'utf8')).join('\n');
}

// UUID stable, pour que deux builds successifs produisent le même JSON.
function stableUuid(seed) {
  const h = createHash('sha1').update(seed).digest('hex');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
}

const WEBHOOK_TYPES = ['n8n-nodes-base.formTrigger', 'n8n-nodes-base.webhook'];

export class Workflow {
  constructor({ id, name, errorWorkflow = null }) {
    this.id = id;
    this.name = name;
    this.errorWorkflow = errorWorkflow;
    this.nodes = [];
    this.connections = {};
  }

  // extra : { credentials: { ollamaApi: 'Ollama local' }, onError, retryOnFail, maxTries, ... }
  add(name, [type, typeVersion], parameters, position, extra = {}) {
    if (this.nodes.some((n) => n.name === name)) throw new Error(`Nœud en double : ${name}`);
    // Les déclencheurs à URL (formulaire, webhook) exigent un webhookId pour que n8n enregistre leur chemin.
    const webhook = WEBHOOK_TYPES.includes(type) ? { webhookId: stableUuid(`${this.id}/${name}/webhook`) } : {};
    this.nodes.push({ id: stableUuid(`${this.id}/${name}`), name, type, typeVersion, position, parameters, ...webhook, ...extra });
    return name;
  }

  connect(from, to, { type = 'main', output = 0, input = 0 } = {}) {
    const byType = (this.connections[from] ??= {});
    const outputs = (byType[type] ??= []);
    while (outputs.length <= output) outputs.push([]);
    outputs[output].push({ node: to, type, index: input });
  }

  sticky(name, content, position, [width, height] = [420, 240]) {
    return this.add(name, ['n8n-nodes-base.stickyNote', 1], { content, width, height }, position);
  }

  // credentialIds : { 'Ollama local': '<id>' }. Sans table, seuls les noms sont écrits :
  // l'utilisateur resélectionne les identifiants après un import manuel.
  toJSON({ credentialIds = null } = {}) {
    const nodes = this.nodes.map((n) => {
      if (!n.credentials) return n;
      const credentials = Object.fromEntries(
        Object.entries(n.credentials).map(([key, name]) => [key, credentialIds ? { id: credentialIds[name], name } : { name }]),
      );
      return { ...n, credentials };
    });
    return {
      id: this.id,
      name: this.name,
      active: false,
      nodes,
      connections: this.connections,
      settings: { executionOrder: 'v1', ...(this.errorWorkflow ? { errorWorkflow: this.errorWorkflow } : {}) },
      pinData: {},
      tags: [],
    };
  }
}
