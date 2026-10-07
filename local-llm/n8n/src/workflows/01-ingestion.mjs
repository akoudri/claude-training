import { Workflow } from '../builder.mjs';
import { CREDS, EMBEDDING_MODEL, IDS, NODE, PATHS, TABLE } from '../constants.mjs';

export default function build() {
  const wf = new Workflow({ id: IDS.ingestion, name: '01 – Ingestion des documents', errorWorkflow: IDS.alerte });
  wf.sticky('Note', [
    '## Ingestion',
    'Prépare la **mémoire documentaire** de l’agent : chaque document de `documents/` est découpé en extraits de 1000 caractères, transformé en vecteurs par `bge-m3`, puis stocké dans la table `n8n_vectors`.',
    'L’index est **reconstruit entièrement** à chaque lancement : simple et sans doublon.',
    'Mêmes réglages de découpage qu’Open WebUI, pour comparer les deux systèmes à corpus égal.',
  ].join('\n\n'), [-40, -320], [700, 260]);
  wf.add('Démarrer', NODE.manualTrigger, {}, [0, 0]);
  wf.add("Vider l'index", NODE.postgres, { operation: 'executeQuery', query: `DROP TABLE IF EXISTS ${TABLE};`, options: {} }, [220, 0], { credentials: { postgres: CREDS.postgres } });
  wf.add('Lire les documents', NODE.readWriteFile, { operation: 'read', fileSelector: `${PATHS.documents}/*.{docx,pdf,md}`, options: {} }, [440, 0], { executeOnce: true });
  wf.add('Nommer la source', NODE.code, {
    jsCode: [
      "// Métadonnée « source » = nom du fichier : sert au filtrage par document dans l'analyse.",
      'return $input.all().map((item) => ({ json: { source: item.binary.data.fileName }, binary: item.binary }));',
    ].join('\n'),
  }, [660, 0]);
  wf.add('Indexer', NODE.pgVector, { mode: 'insert', tableName: TABLE, embeddingBatchSize: 32, options: {} }, [900, 0], { credentials: { postgres: CREDS.postgres } });
  wf.add('Charger le document', NODE.dataLoader, {
    dataType: 'binary',
    binaryMode: 'allInputData',
    loader: 'auto',
    textSplittingMode: 'custom',
    options: { metadata: { metadataValues: [{ name: 'source', value: '={{ $json.source }}' }] } },
  }, [980, 220]);
  wf.add('Découper', NODE.textSplitter, { chunkSize: 1000, chunkOverlap: 150, options: {} }, [1060, 420]);
  wf.add('Embeddings bge-m3', NODE.embeddingsOllama, { model: EMBEDDING_MODEL }, [820, 220], { credentials: { ollamaApi: CREDS.ollama } });
  wf.add('Bilan', NODE.postgres, {
    operation: 'executeQuery',
    query: `SELECT metadata->>'source' AS source, count(*) AS extraits FROM ${TABLE} GROUP BY 1 ORDER BY 1;`,
    options: {},
  }, [1180, 0], { credentials: { postgres: CREDS.postgres }, executeOnce: true });

  wf.connect('Démarrer', "Vider l'index");
  wf.connect("Vider l'index", 'Lire les documents');
  wf.connect('Lire les documents', 'Nommer la source');
  wf.connect('Nommer la source', 'Indexer');
  wf.connect('Indexer', 'Bilan');
  wf.connect('Charger le document', 'Indexer', { type: 'ai_document' });
  wf.connect('Découper', 'Charger le document', { type: 'ai_textSplitter' });
  wf.connect('Embeddings bge-m3', 'Indexer', { type: 'ai_embedding' });
  return wf;
}
