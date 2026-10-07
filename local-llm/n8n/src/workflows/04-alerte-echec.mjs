import { Workflow } from '../builder.mjs';
import { CREDS, IDS, NODE, PATHS } from '../constants.mjs';
import { jsonFromFile, readFile } from '../parts.mjs';

export default function build() {
  const wf = new Workflow({ id: IDS.alerte, name: "04 – Alerte d'échec" });
  wf.sticky('Note', [
    "## Alerte d'échec",
    "Déclaré comme *workflow d'erreur* des autres workflows : n8n l'exécute quand l'un d'eux s'arrête sur une erreur non prévue (exécutions de production uniquement).",
    "Le mail ne contient **que** le nom du workflow, l'étape et l'heure. Le message d'erreur peut contenir des extraits de documents confidentiels : il reste dans l'historique de n8n.",
  ].join('\n\n'), [-40, -280], [620, 240]);
  wf.add('Erreur', NODE.errorTrigger, {}, [0, 0]);
  wf.add('Lire la notification', NODE.readWriteFile, readFile(PATHS.notification), [220, 0]);
  wf.add('Décoder la notification', NODE.extractFromFile, jsonFromFile('notification'), [440, 0]);
  wf.add("Envoyer l'alerte", NODE.emailSend, {
    fromEmail: '={{ $json.notification.expediteur }}',
    toEmail: '={{ $json.notification.destinataire }}',
    subject: "={{ '[n8n] Échec – ' + $('Erreur').item.json.workflow.name }}",
    emailFormat: 'text',
    text: "={{ 'Le workflow « ' + $('Erreur').item.json.workflow.name + ' » a échoué à l\\'étape « ' + ($('Erreur').item.json.execution.lastNodeExecuted || 'inconnue') + ' » le ' + $now.toFormat('dd/MM/yyyy HH:mm') + '.\\n\\nDétail : historique des exécutions de n8n (exécution ' + ($('Erreur').item.json.execution.id || '?') + ').' }}",
    options: {},
  }, [660, 0], { credentials: { smtp: CREDS.smtp } });
  wf.connect('Erreur', 'Lire la notification');
  wf.connect('Lire la notification', 'Décoder la notification');
  wf.connect('Décoder la notification', "Envoyer l'alerte");
  return wf;
}
