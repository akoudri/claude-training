// Constantes partagées par les modules de workflows.

export const IDS = {
  ingestion: 'cnfIngestion0001',
  analyse: 'cnfAnalyse000002',
  formulaire: 'cnfFormulaire02a',
  synthese: 'cnfSynthese00003',
  alerte: 'cnfAlerteEchec04',
  testSynthese: 'cnfTestSynth0090',
  testAnalyse: 'cnfTestAnaly0091',
};

// Noms des identifiants créés dans l'interface de n8n (jamais versionnés).
export const CREDS = { ollama: 'Ollama local', postgres: 'Postgres rag', smtp: 'Gmail SMTP' };

export const MODEL = 'granite4.2:8b';
export const EMBEDDING_MODEL = 'bge-m3';
export const TABLE = 'n8n_vectors';
// Pas de numCtx : le contexte vient de OLLAMA_CONTEXT_LENGTH (sinon rechargement du modèle).
export const OLLAMA_OPTIONS = { temperature: 0.1, think: false };

export const PATHS = {
  documents: '/data/documents',
  reports: '/data/reports',
  dictionary: '/data/config/sensitive-terms.json',
  notification: '/data/config/notification.json',
};

// [type, typeVersion] relevés sur n8n 2.41.6 (`n8n export:nodes`).
export const NODE = {
  manualTrigger: ['n8n-nodes-base.manualTrigger', 1],
  errorTrigger: ['n8n-nodes-base.errorTrigger', 1],
  formTrigger: ['n8n-nodes-base.formTrigger', 2.6],
  subWorkflowTrigger: ['n8n-nodes-base.executeWorkflowTrigger', 1.1],
  executeWorkflow: ['n8n-nodes-base.executeWorkflow', 1.4],
  postgres: ['n8n-nodes-base.postgres', 2.7],
  readWriteFile: ['n8n-nodes-base.readWriteFile', 1.1],
  extractFromFile: ['n8n-nodes-base.extractFromFile', 1.1],
  convertToFile: ['n8n-nodes-base.convertToFile', 1.1],
  code: ['n8n-nodes-base.code', 2],
  if: ['n8n-nodes-base.if', 2.3],
  loop: ['n8n-nodes-base.splitInBatches', 3],
  emailSend: ['n8n-nodes-base.emailSend', 2.1],
  agent: ['@n8n/n8n-nodes-langchain.agent', 3.1],
  chainLlm: ['@n8n/n8n-nodes-langchain.chainLlm', 1.9],
  chatOllama: ['@n8n/n8n-nodes-langchain.lmChatOllama', 1],
  embeddingsOllama: ['@n8n/n8n-nodes-langchain.embeddingsOllama', 1],
  pgVector: ['@n8n/n8n-nodes-langchain.vectorStorePGVector', 1.3],
  dataLoader: ['@n8n/n8n-nodes-langchain.documentDefaultDataLoader', 1.1],
  textSplitter: ['@n8n/n8n-nodes-langchain.textSplitterRecursiveCharacterTextSplitter', 1],
  outputParser: ['@n8n/n8n-nodes-langchain.outputParserStructured', 1.3],
};
