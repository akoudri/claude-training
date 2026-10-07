// Fragments de paramètres réutilisés par plusieurs workflows.
import { libCode } from './builder.mjs';
import { MODEL, OLLAMA_OPTIONS } from './constants.mjs';

export function ifTrue(expression) {
  return {
    conditions: {
      options: { caseSensitive: true, leftValue: '', typeValidation: 'strict', version: 2 },
      conditions: [{ id: 'condition-1', leftValue: expression, rightValue: '', operator: { type: 'boolean', operation: 'true', singleValue: true } }],
      combinator: 'and',
    },
    options: {},
  };
}

// Le sous-workflow appelé utilise « Accept all data » : les items sont transmis tels quels.
export function callWorkflow(workflowId, wait) {
  return {
    source: 'database',
    workflowId: { __rl: true, value: workflowId, mode: 'id' },
    workflowInputs: { mappingMode: 'defineBelow', value: {}, matchingColumns: [], schema: [], attemptToConvertTypes: false, convertFieldsToString: true },
    mode: 'once',
    options: { waitForSubWorkflow: wait },
  };
}

export function readFile(filePath) {
  return { operation: 'read', fileSelector: filePath, options: {} };
}

export function jsonFromFile(destinationKey) {
  return { operation: 'fromJson', binaryPropertyName: 'data', destinationKey, options: {} };
}

export function chatModel() {
  return { model: MODEL, options: { ...OLLAMA_OPTIONS } };
}

export function codeNode(libs, body) {
  return { jsCode: `${libCode(...libs)}\n// ---- Code propre au nœud ----\n${body}` };
}
