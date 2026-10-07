import { Workflow } from '../builder.mjs';
import { IDS, NODE } from '../constants.mjs';
import { callWorkflow } from '../parts.mjs';

const CAS_1 = `return [{ json: {
  mode: 'succes', motif: null, horodatage: new Date().toISOString(),
  statistiques: { total: 3, couverte: 1, partielle: 1, non_couverte: 1, indeterminee: 0 },
  lignes: [
    { id: 'EX-01', intitule: 'Inventaire des modèles pour Acme Défense', statut: 'couverte' },
    { id: 'EX-04', intitule: 'Formation dispensée par Novaltis', statut: 'partielle' },
    { id: 'EX-09', intitule: 'Support (contact : jeanne.martin@novaltis.example)', statut: 'non_couverte' },
  ],
} }];`;

const CAS_2 = `return [{ json: {
  mode: 'succes', motif: null, horodatage: new Date().toISOString(),
  statistiques: { total: 1, couverte: 1, partielle: 0, non_couverte: 0, indeterminee: 0 },
  lignes: [{ id: 'EX-01', intitule: 'Intégration AcmeCorp', statut: 'couverte' }],
} }];`;

export default function build() {
  const wf = new Workflow({ id: IDS.testSynthese, name: '90 – Test synthèse' });
  wf.sticky('Note', [
    '## Test du workflow 03',
    'Cas 1 : le contrôle passe, le mail contient le tableau pseudonymisé.',
    'Cas 2 : « AcmeCorp » n’est pas remplacé (limite de mot) mais le contrôle strict le détecte : mail réduit aux statistiques.',
    'Cas 3 : relancer après avoir renommé `n8n/config/sensitive-terms.json` : les deux mails sont réduits (« dictionnaire indisponible »).',
  ].join('\n\n'), [-40, -320], [760, 260]);
  wf.add('Démarrer', NODE.manualTrigger, {}, [0, 0]);
  wf.add('Cas 1 : contrôle OK', NODE.code, { jsCode: CAS_1 }, [220, 0]);
  wf.add('Envoyer le cas 1', NODE.executeWorkflow, callWorkflow(IDS.synthese, true), [440, 0]);
  wf.add('Cas 2 : terme résiduel', NODE.code, { jsCode: CAS_2 }, [660, 0]);
  wf.add('Envoyer le cas 2', NODE.executeWorkflow, callWorkflow(IDS.synthese, true), [880, 0]);
  wf.connect('Démarrer', 'Cas 1 : contrôle OK');
  wf.connect('Cas 1 : contrôle OK', 'Envoyer le cas 1');
  wf.connect('Envoyer le cas 1', 'Cas 2 : terme résiduel');
  wf.connect('Cas 2 : terme résiduel', 'Envoyer le cas 2');
  return wf;
}
