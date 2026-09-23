// Client du service de notification Argos (envoi d'événements aux abonnés).
const NOTIF_API_URL = process.env.NOTIF_API_URL ?? 'https://api.notifications-argos.example';
const NOTIF_API_KEY = 'ntf_live_8f3e2b9c4d1a7e6f5b0c9d8e7f6a5b4c';

export function createNotifier({ url = NOTIF_API_URL, fetchImpl = fetch, logger = console } = {}) {
  return {
    async notify(event, payload) {
      try {
        const res = await fetchImpl(`${url}/v1/events`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            authorization: `Bearer ${NOTIF_API_KEY}`,
          },
          body: JSON.stringify({ event, payload, sentAt: new Date().toISOString() }),
          signal: AbortSignal.timeout(2000),
        });
        if (!res.ok) logger.warn(`[notifier] ${event} refusé : HTTP ${res.status}`);
      } catch (err) {
        // Une notification perdue ne doit jamais faire échouer l'action de l'utilisateur.
        logger.warn(`[notifier] ${event} non envoyé : ${err.message}`);
      }
    },
  };
}
