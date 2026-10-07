import { Workflow } from '../builder.mjs';
import { IDS, NODE } from '../constants.mjs';
import { callWorkflow } from '../parts.mjs';

export default function build() {
  const wf = new Workflow({ id: IDS.testAnalyse, name: '91 – Test analyse' });
  wf.sticky('Note', [
    '## Test du workflow 02 sur le corpus fictif',
    'Puis : `node n8n/scripts/evaluate-report.mjs reports/<dernier rapport>`.',
  ].join('\n\n'), [-40, -260], [560, 180]);
  wf.add('Démarrer', NODE.manualTrigger, {}, [0, 0]);
  wf.add('Documents de test', NODE.code, {
    jsCode: "return [{ json: { referentiel: 'sow-exemple.md', analyse: 'Proposition – Projet Héron, v2.md' } }];",
  }, [220, 0]);
  wf.add('Analyser', NODE.executeWorkflow, callWorkflow(IDS.analyse, true), [440, 0]);
  wf.connect('Démarrer', 'Documents de test');
  wf.connect('Documents de test', 'Analyser');
  return wf;
}
