import { Workflow } from '../builder.mjs';
import { CREDS, EMBEDDING_MODEL, IDS, NODE, PATHS, TABLE } from '../constants.mjs';
import { callWorkflow, chatModel, codeNode, ifTrue } from '../parts.mjs';

const EXTRACTION_PROMPT = `You extract the requirements and deliverables from a statement of work.
Return every requirement or deliverable stated in the document, in document order.
- id: the identifier used in the document (for example "EX-01" or "WP1-D2"); if there is none, number them E1, E2, ...
- intitule: a short title in the document's language (12 words at most)
- description: one or two sentences restating what is required, in the document's language
- type: "livrable" if it is something to deliver (report, model, tool, training material), otherwise "exigence"
Do not invent items. Ignore the table of contents, page headers and footers.`;

const AGENT_SYSTEM = `You assess whether a proposal covers ONE requirement of a statement of work.
Tools:
- chercher_dans_document_analyse searches only the proposal. Use it first, with the key terms of the requirement.
- chercher_dans_corpus searches all documents. Use it only to understand a term.
Make at most 3 searches, then answer.
Verdict rules:
- "couverte": a passage of the proposal fully satisfies the requirement. You MUST cite it.
- "partielle": the proposal addresses the subject but not the whole requirement (smaller quantity, reduced scope). Cite it.
- "non_couverte": your searches of the proposal found nothing relevant.
- "indeterminee": you cannot decide.
Citations: copy short exact excerpts (300 characters at most) and the source file name exactly as given in the search results metadata.
Write the justification in French, in one to three sentences.`;

const EXIGENCES_SCHEMA = {
  type: 'object',
  properties: {
    exigences: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          intitule: { type: 'string' },
          description: { type: 'string' },
          type: { type: 'string', enum: ['exigence', 'livrable'] },
        },
        required: ['id', 'intitule', 'description', 'type'],
      },
    },
  },
  required: ['exigences'],
};

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    statut: { type: 'string', enum: ['couverte', 'partielle', 'non_couverte', 'indeterminee'] },
    justification: { type: 'string' },
    citations: {
      type: 'array',
      items: { type: 'object', properties: { source: { type: 'string' }, extrait: { type: 'string' } }, required: ['source', 'extrait'] },
    },
  },
  required: ['statut', 'justification', 'citations'],
};

const DOC_ANALYSE = "={{ $('Initialiser').first().json.analyse }}";
const POSTGRES = { credentials: { postgres: CREDS.postgres } };
const OLLAMA = { credentials: { ollamaApi: CREDS.ollama } };

export default function build() {
  const wf = new Workflow({ id: IDS.analyse, name: '02 – Analyse de conformité', errorWorkflow: IDS.alerte });

  wf.sticky('Note workflow', [
    '## Partie « workflow » : les étapes sont fixées',
    "Validation des documents → reconstitution du référentiel → **extraction des exigences** en un seul appel au LLM (le document entier tient dans le contexte : plus fiable qu'une recherche).",
  ].join('\n\n'), [-40, -340], [1100, 220]);
  wf.sticky('Note agent', [
    '## Partie « agent » : le LLM décide',
    "Pour **chaque** exigence, un agent choisit ses recherches (3 au maximum) dans la proposition ou dans le corpus, puis rend un verdict structuré. La tâche est courte et bornée : à la portée d'un modèle de 8B.",
    'Ouvrir une exécution et cliquer sur le nœud *Analyser l’exigence* pour voir chaque appel d’outil.',
  ].join('\n\n'), [1500, -340], [900, 240]);
  wf.sticky('Note rapport', [
    '## Rapport et synthèse',
    'Le rapport complet reste dans `reports/`. Le workflow 03 envoie une synthèse pseudonymisée.',
    'Règle contrôlée en code : un verdict « couverte » sans citation du document analysé devient « indeterminee ».',
  ].join('\n\n'), [2600, -340], [760, 220]);

  // --- Entrée et validation ---
  wf.add('Entrée', NODE.subWorkflowTrigger, { inputSource: 'passthrough' }, [0, 0]);
  wf.add('Initialiser', NODE.code, { jsCode: [
    'const p = $input.first().json;',
    "const referentiel = String(p.referentiel ?? p['Document référentiel'] ?? '').trim();",
    "const analyse = String(p.analyse ?? p['Document analysé'] ?? '').trim();",
    'return [{ json: { referentiel, analyse, debut: new Date().toISOString() } }];',
  ].join('\n') }, [220, 0]);
  wf.add('Documents indexés', NODE.postgres, {
    operation: 'executeQuery',
    query: `SELECT DISTINCT metadata->>'source' AS source FROM ${TABLE} ORDER BY 1;`,
    options: {},
  }, [440, 0], { ...POSTGRES, alwaysOutputData: true, executeOnce: true });
  wf.add('Vérifier les documents', NODE.code, codeNode(['pseudonymize.js', 'report.js'], [
    "const p = $('Initialiser').first().json;",
    'const sources = $input.all().map((i) => i.json.source).filter(Boolean);',
    'const manquants = [p.referentiel, p.analyse].filter((d) => !sources.includes(d));',
    '// Le motif ne contient que des comptes : aucun nom de document, saisi ou indexé.',
    'const motif = manquants.length ? missingDocsMotif(manquants, sources) : null;',
    'return [{ json: { ok: manquants.length === 0, motif } }];',
  ].join('\n')), [660, 0]);
  wf.add('Documents présents ?', NODE.if, ifTrue('={{ $json.ok }}'), [880, 0]);

  // --- Extraction des exigences (workflow) ---
  wf.add('Extraits du référentiel', NODE.postgres, {
    operation: 'executeQuery',
    query: `SELECT text, metadata FROM ${TABLE} WHERE metadata->>'source' = $1;`,
    options: { queryReplacement: "={{ [$('Initialiser').first().json.referentiel] }}" },
  }, [1100, -100], POSTGRES);
  wf.add('Reconstituer le référentiel', NODE.code, codeNode(['verdict.js'], [
    'const texte = orderChunks($input.all().map((i) => i.json));',
    'checkReferentielLength(texte);',
    'return [{ json: { texte } }];',
  ].join('\n')), [1320, -100]);
  wf.add('Extraire les exigences', NODE.chainLlm, {
    promptType: 'define',
    text: `=${EXTRACTION_PROMPT}\n\nDocument:\n{{ $json.texte }}`,
    hasOutputParser: true,
  }, [1540, -100], { retryOnFail: true, maxTries: 3, waitBetweenTries: 1000, onError: 'continueErrorOutput' });
  wf.add('Modèle (extraction)', NODE.chatOllama, chatModel(), [1500, 120], OLLAMA);
  wf.add('Format des exigences', NODE.outputParser, { schemaType: 'manual', inputSchema: JSON.stringify(EXIGENCES_SCHEMA, null, 2) }, [1660, 120]);
  wf.add('Lister les exigences', NODE.code, { jsCode: [
    'const out = $json.output ?? {};',
    'const brutes = Array.isArray(out.exigences) ? out.exigences : [];',
    'const liste = brutes.slice(0, 25);',
    "if (liste.length === 0) return [{ json: { _echec: true, motif: 'Aucune exigence identifiée dans le document référentiel.' } }];",
    'return liste.map((e, i) => ({ json: {',
    '  id: String(e.id || `E${i + 1}`),',
    "  intitule: String(e.intitule || ''),",
    '  extraites: brutes.length,',
    "  description: String(e.description || ''),",
    "  type: e.type === 'livrable' ? 'livrable' : 'exigence',",
    '} }));',
  ].join('\n') }, [1780, -100]);
  wf.add('Exigences trouvées ?', NODE.if, ifTrue('={{ !$json._echec }}'), [2000, -100]);

  // --- Boucle : un agent par exigence ---
  wf.add('Exigences à analyser', NODE.loop, { options: {} }, [2220, -120]);
  wf.add("Analyser l'exigence", NODE.agent, {
    promptType: 'define',
    text: "={{ 'Requirement ' + $json.id + ' (' + $json.type + '): ' + $json.intitule + '\\n' + $json.description + '\\n\\nAnalysed document (proposal): ' + $('Initialiser').first().json.analyse }}",
    hasOutputParser: true,
    options: { systemMessage: AGENT_SYSTEM, maxIterations: 4, forceToolCallOnFirstIteration: true, enableStreaming: false },
  }, [2460, 40], { retryOnFail: true, maxTries: 2, waitBetweenTries: 1000, onError: 'continueErrorOutput' });
  wf.add('Modèle (agent)', NODE.chatOllama, chatModel(), [2340, 280], OLLAMA);
  wf.add('chercher_dans_document_analyse', NODE.pgVector, {
    mode: 'retrieve-as-tool',
    toolDescription: "Recherche dans le document analysé (la proposition). Entrée : une requête courte reprenant les termes clés de l'exigence.",
    tableName: TABLE,
    topK: 4,
    includeDocumentMetadata: true,
    options: { metadata: { metadataValues: [{ name: 'source', value: DOC_ANALYSE }] } },
  }, [2480, 280], POSTGRES);
  wf.add('chercher_dans_corpus', NODE.pgVector, {
    mode: 'retrieve-as-tool',
    toolDescription: 'Recherche dans tous les documents indexés. À utiliser seulement pour comprendre un terme.',
    tableName: TABLE,
    topK: 4,
    includeDocumentMetadata: true,
    options: {},
  }, [2620, 280], POSTGRES);
  wf.add('Embeddings (recherche)', NODE.embeddingsOllama, { model: EMBEDDING_MODEL }, [2560, 480], OLLAMA);
  wf.add('Format du verdict', NODE.outputParser, { schemaType: 'manual', inputSchema: JSON.stringify(VERDICT_SCHEMA, null, 2) }, [2760, 280]);
  wf.add('Normaliser le verdict', NODE.code, codeNode(['verdict.js'], [
    "const analyse = $('Initialiser').first().json.analyse;",
    "const exigence = $('Exigences à analyser').first().json;",
    'return [{ json: { ...exigence, ...normalizeVerdict($json.output, analyse) } }];',
  ].join('\n')), [2860, -20]);
  wf.add('Verdict en erreur', NODE.code, codeNode(['verdict.js'], [
    "const exigence = $('Exigences à analyser').first().json;",
    "const message = $json.error?.message ?? $json.error ?? '';",
    'return [{ json: { ...exigence, ...errorVerdict(message) } }];',
  ].join('\n')), [2860, 140]);

  // --- Rapport et synthèse ---
  wf.add('Assembler le rapport', NODE.code, codeNode(['pseudonymize.js', 'report.js'], [
    "const p = $('Initialiser').first().json;",
    'const lignes = $input.all().map(({ json: l }) => ({',
    '  id: l.id, type: l.type, intitule: l.intitule, statut: l.statut,',
    '  justification: l.justification, citations: l.citations ?? [],',
    '}));',
    'const extraites = $input.first().json.extraites ?? lignes.length;',
    'const debut = new Date(p.debut);',
    'const fin = new Date();',
    'return [{ json: {',
    '  nomFichier: reportFileName(fin),',
    '  rapport: buildReport({ referentiel: p.referentiel, analyse: p.analyse, debut, fin, lignes, extraites }),',
    "  synthese: { mode: 'succes', motif: null, statistiques: computeStats(lignes),",
    '    lignes: lignes.map(({ id, intitule, statut }) => ({ id, intitule, statut })), extraites, horodatage: fin.toISOString() },',
    '} }];',
  ].join('\n')), [2460, -300]);
  wf.add('Convertir le rapport', NODE.convertToFile, {
    operation: 'toText',
    sourceProperty: 'rapport',
    binaryPropertyName: 'data',
    options: { fileName: '={{ $json.nomFichier }}', encoding: 'utf8' },
  }, [2680, -300]);
  wf.add('Écrire le rapport', NODE.readWriteFile, {
    operation: 'write',
    fileName: `={{ '${PATHS.reports}/' + $('Assembler le rapport').first().json.nomFichier }}`,
    dataPropertyName: 'data',
    options: {},
  }, [2900, -300]);
  wf.add('Préparer la synthèse', NODE.code, { jsCode: "return [{ json: $('Assembler le rapport').first().json.synthese }];" }, [3120, -300]);
  wf.add("Préparer l'échec", NODE.code, { jsCode: [
    "const motif = $input.first().json.motif || 'Extraction des exigences impossible : sortie du modèle invalide après 3 tentatives.';",
    "return [{ json: { mode: 'echec', motif, statistiques: null, lignes: [], horodatage: new Date().toISOString() } }];",
  ].join('\n') }, [3120, 200]);
  wf.add('Envoyer la synthèse', NODE.executeWorkflow, callWorkflow(IDS.synthese, true), [3360, -40]);

  // --- Connexions ---
  wf.connect('Entrée', 'Initialiser');
  wf.connect('Initialiser', 'Documents indexés');
  wf.connect('Documents indexés', 'Vérifier les documents');
  wf.connect('Vérifier les documents', 'Documents présents ?');
  wf.connect('Documents présents ?', 'Extraits du référentiel', { output: 0 });
  wf.connect('Documents présents ?', "Préparer l'échec", { output: 1 });
  wf.connect('Extraits du référentiel', 'Reconstituer le référentiel');
  wf.connect('Reconstituer le référentiel', 'Extraire les exigences');
  wf.connect('Modèle (extraction)', 'Extraire les exigences', { type: 'ai_languageModel' });
  wf.connect('Format des exigences', 'Extraire les exigences', { type: 'ai_outputParser' });
  wf.connect('Extraire les exigences', 'Lister les exigences', { output: 0 });
  wf.connect('Extraire les exigences', "Préparer l'échec", { output: 1 });
  wf.connect('Lister les exigences', 'Exigences trouvées ?');
  wf.connect('Exigences trouvées ?', 'Exigences à analyser', { output: 0 });
  wf.connect('Exigences trouvées ?', "Préparer l'échec", { output: 1 });
  wf.connect('Exigences à analyser', 'Assembler le rapport', { output: 0 });
  wf.connect('Exigences à analyser', "Analyser l'exigence", { output: 1 });
  wf.connect('Modèle (agent)', "Analyser l'exigence", { type: 'ai_languageModel' });
  wf.connect('chercher_dans_document_analyse', "Analyser l'exigence", { type: 'ai_tool' });
  wf.connect('chercher_dans_corpus', "Analyser l'exigence", { type: 'ai_tool' });
  wf.connect('Embeddings (recherche)', 'chercher_dans_document_analyse', { type: 'ai_embedding' });
  wf.connect('Embeddings (recherche)', 'chercher_dans_corpus', { type: 'ai_embedding' });
  wf.connect('Format du verdict', "Analyser l'exigence", { type: 'ai_outputParser' });
  wf.connect("Analyser l'exigence", 'Normaliser le verdict', { output: 0 });
  wf.connect("Analyser l'exigence", 'Verdict en erreur', { output: 1 });
  wf.connect('Normaliser le verdict', 'Exigences à analyser');
  wf.connect('Verdict en erreur', 'Exigences à analyser');
  wf.connect('Assembler le rapport', 'Convertir le rapport');
  wf.connect('Convertir le rapport', 'Écrire le rapport');
  wf.connect('Écrire le rapport', 'Préparer la synthèse');
  wf.connect('Préparer la synthèse', 'Envoyer la synthèse');
  wf.connect("Préparer l'échec", 'Envoyer la synthèse');
  return wf;
}
