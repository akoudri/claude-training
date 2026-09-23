import express from 'express';
import { existsSync } from 'node:fs';
import { ticketsRouter } from './routes/tickets.js';
import { findAll } from './repositories/tickets.js';
import { countByStatus } from './services/stats.js';

export function createApp({ db, notifier, staticDir }) {
  const app = express();
  app.use(express.json());

  app.get('/api/health', (req, res) => res.json({ status: 'ok' }));
  app.get('/api/stats', (req, res) => res.json(countByStatus(findAll(db))));
  app.use('/api/tickets', ticketsRouter({ db, notifier }));

  if (staticDir && existsSync(staticDir)) {
    app.use(express.static(staticDir));
  }

  app.use((err, req, res, _next) => {
    console.error(err);
    res.status(500).json({ error: 'Erreur interne' });
  });

  return app;
}
