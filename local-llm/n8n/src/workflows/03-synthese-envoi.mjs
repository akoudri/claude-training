import { Workflow } from '../builder.mjs';
import { CREDS, IDS, NODE, PATHS } from '../constants.mjs';
import { codeNode, jsonFromFile, readFile } from '../parts.mjs';

const COMPOSER = `
const entree = $('Entrée').first().json;
let brut = null;
try {
  brut = $('Décoder le dictionnaire').first().json.dictionnaire ?? null;
} catch (e) {
  brut = null;
}
const dict = loadTerms(brut);
const notification = $('Décoder la notification').first().json.notification ?? {};
if (!notification.destinataire || !notification.expediteur) {
  throw new Error('notification.json incomplet : champs destinataire et expediteur requis.');
}
const mail = buildMail({
  mode: entree.mode,
  motif: entree.motif,
  statistiques: entree.statistiques,
  lignes: entree.lignes ?? [],
  extraites: entree.extraites,
  dict,
  dateLabel: formatDateLabel(new Date(entree.horodatage ?? Date.now())),
});
return [{ json: { ...mail, destinataire: notification.destinataire, expediteur: notification.expediteur } }];
`;

export default function build() {
  const wf = new Workflow({ id: IDS.synthese, name: '03 – Synthèse et envoi', errorWorkflow: IDS.alerte });
  wf.sticky('Note', [
    '## Synthèse pseudonymisée',
    '1. Les intitulés sont pseudonymisés avec le dictionnaire `n8n/config/sensitive-terms.json` (remplacement déterministe, pas de LLM).',
    "2. **Contrôle bloquant** : si un terme du dictionnaire subsiste, ou si le dictionnaire manque, le mail est réduit aux statistiques.",
    '3. Justifications, citations et noms de documents ne sortent **jamais** de la machine.',
  ].join('\n\n'), [-40, -320], [760, 260]);
  wf.add('Entrée', NODE.subWorkflowTrigger, { inputSource: 'passthrough' }, [0, 0]);
  wf.add('Lire le dictionnaire', NODE.readWriteFile, readFile(PATHS.dictionary), [220, 0], { onError: 'continueRegularOutput', alwaysOutputData: true });
  wf.add('Décoder le dictionnaire', NODE.extractFromFile, jsonFromFile('dictionnaire'), [440, 0], { onError: 'continueRegularOutput', alwaysOutputData: true });
  wf.add('Lire la notification', NODE.readWriteFile, readFile(PATHS.notification), [660, 0], { executeOnce: true });
  wf.add('Décoder la notification', NODE.extractFromFile, jsonFromFile('notification'), [880, 0]);
  wf.add('Composer le mail', NODE.code, codeNode(['pseudonymize.js', 'report.js'], COMPOSER), [1100, 0]);
  wf.add('Envoyer', NODE.emailSend, {
    fromEmail: '={{ $json.expediteur }}',
    toEmail: '={{ $json.destinataire }}',
    subject: '={{ $json.subject }}',
    emailFormat: 'text',
    text: '={{ $json.text }}',
    options: {},
  }, [1320, 0], { credentials: { smtp: CREDS.smtp } });
  wf.connect('Entrée', 'Lire le dictionnaire');
  wf.connect('Lire le dictionnaire', 'Décoder le dictionnaire');
  wf.connect('Décoder le dictionnaire', 'Lire la notification');
  wf.connect('Lire la notification', 'Décoder la notification');
  wf.connect('Décoder la notification', 'Composer le mail');
  wf.connect('Composer le mail', 'Envoyer');
  return wf;
}
