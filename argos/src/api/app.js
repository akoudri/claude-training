import express from 'express';
import { existsSync } from 'node:fs';
import { ticketsRouter } from './routes/tickets.js';
import { findAll } from './repositories/tickets.js';
import { countByStatus } from './services/stats.js';

export function createApp({ db, notifier, staticDir }) {
  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '64kb' }));

  app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
  app.get('/api/stats', (req, res) => res.json(countByStatus(findAll(db))));
  app.use('/api/tickets', ticketsRouter({ db, notifier }));

  if (staticDir && existsSync(staticDir)) {
    app.use(express.static(staticDir));
  }

  // Les erreurs 4xx d'Express (JSON mal formé, corps trop volumineux…) gardent leur code ;
  // seules les vraies erreurs serveur sont journalisées.
  app.use((err, req, res, _next) => {
    const status = err.status ?? err.statusCode ?? 500;
    if (status >= 500) {
      console.error(err);
      return res.status(500).json({ error: 'Erreur interne' });
    }
    res.status(status).json({ error: 'Requête invalide' });
  });

  return app;
}
