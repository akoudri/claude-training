import { Workflow } from '../builder.mjs';
import { IDS, NODE } from '../constants.mjs';
import { callWorkflow } from '../parts.mjs';

export default function build() {
  const wf = new Workflow({ id: IDS.formulaire, name: "02a – Formulaire d'analyse", errorWorkflow: IDS.alerte });
  wf.sticky('Note', [
    "## Point d'entrée",
    'Formulaire : http://localhost:5678/form/analyse-conformite',
    "Il lance le workflow 02 **sans attendre** sa fin : l'analyse dure 10 à 20 minutes. Les noms de fichiers sont ceux du dossier `documents/`.",
  ].join('\n\n'), [-40, -300], [620, 220]);
  wf.add('Formulaire', NODE.formTrigger, {
    formTitle: 'Analyse de conformité',
    formDescription: 'Compare un document analysé (proposition) à un document référentiel (cahier des charges). Indiquez les noms de fichiers du dossier documents/.',
    formFields: { values: [
      { fieldLabel: 'Document référentiel', fieldName: 'referentiel', fieldType: 'text', defaultValue: 'sow-exemple.md', requiredField: true },
      { fieldLabel: 'Document analysé', fieldName: 'analyse', fieldType: 'text', defaultValue: 'Proposition – Projet Héron, v2.md', requiredField: true },
    ] },
    responseMode: 'onReceived',
    // Depuis la v2.2 du nœud, le chemin et le texte de confirmation sont des options.
    options: {
      path: 'analyse-conformite',
      respondWithOptions: { values: { respondWith: 'text', formSubmittedText: 'Analyse lancée : rapport dans reports/, synthèse par mail à la fin (10 à 20 minutes).' } },
    },
  }, [0, 0]);
  wf.add("Lancer l'analyse", NODE.executeWorkflow, callWorkflow(IDS.analyse, false), [240, 0]);
  wf.connect('Formulaire', "Lancer l'analyse");
  return wf;
}
