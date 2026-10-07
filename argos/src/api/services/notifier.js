// Client du service de notification Argos (envoi d'événements aux abonnés).
// L'URL et la clé viennent de l'environnement (.env) ; sans elles, les notifications sont
// désactivées plutôt qu'envoyées vers un service par défaut.
export function createNotifier({
  url = process.env.NOTIF_API_URL,
  apiKey = process.env.NOTIF_API_KEY,
  fetchImpl = fetch,
  logger = console,
} = {}) {
  if (!url || !apiKey) {
    logger.warn('[notifier] NOTIF_API_URL ou NOTIF_API_KEY non défini : notifications désactivées');
    return { async notify() {} };
  }

  return {
    async notify(event, payload) {
      try {
        const res = await fetchImpl(`${url}/v1/events`, {
          method: 'POST',
          headers: {
            'content-type': 'application/json',
            authorization: `Bearer ${apiKey}`,
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
