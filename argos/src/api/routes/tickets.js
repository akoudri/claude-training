import { Router } from 'express';
import * as tickets from '../repositories/tickets.js';
import { filterByStatus } from '../services/filters.js';

function badRequest(res, message) {
  return res.status(400).json({ error: message });
}

const MAX_LENGTH = { title: 200, description: 5000, assignee: 100 };

function validate(body, { partial }) {
  if (!partial || body.title !== undefined) {
    if (typeof body.title !== 'string' || body.title.trim() === '') return 'Le titre est obligatoire';
  }
  if (body.description !== undefined && typeof body.description !== 'string') {
    return 'La description doit être un texte';
  }
  if (body.assignee !== undefined && body.assignee !== null && typeof body.assignee !== 'string') {
    return 'Le responsable doit être un texte ou null';
  }
  for (const [field, max] of Object.entries(MAX_LENGTH)) {
    if (typeof body[field] === 'string' && body[field].length > max) {
      return `Le champ ${field} dépasse ${max} caractères`;
    }
  }
  if (body.status !== undefined && !tickets.STATUSES.includes(body.status)) {
    return `Statut invalide (attendu : ${tickets.STATUSES.join(', ')})`;
  }
  if (body.priority !== undefined && !tickets.PRIORITIES.includes(body.priority)) {
    return `Priorité invalide (attendu : ${tickets.PRIORITIES.join(', ')})`;
  }
  return null;
}

export function ticketsRouter({ db, notifier }) {
  const router = Router();

  router.get('/', (req, res) => {
    res.json(filterByStatus(tickets.findAll(db), req.query.status));
  });

  router.get('/:id', (req, res) => {
    const ticket = tickets.findById(db, Number(req.params.id));
    if (!ticket) return res.status(404).json({ error: 'Ticket introuvable' });
    res.json(ticket);
  });

  router.post('/', async (req, res) => {
    const error = validate(req.body ?? {}, { partial: false });
    if (error) return badRequest(res, error);
    const { title, description, priority, assignee } = req.body;
    const ticket = tickets.create(db, { title: title.trim(), description, priority, assignee });
    await notifier.notify('ticket.created', { id: ticket.id, title: ticket.title });
    res.status(201).json(ticket);
  });

  router.patch('/:id', async (req, res) => {
    const id = Number(req.params.id);
    const before = tickets.findById(db, id);
    if (!before) return res.status(404).json({ error: 'Ticket introuvable' });
    const error = validate(req.body ?? {}, { partial: true });
    if (error) return badRequest(res, error);
    const changes = { ...req.body };
    if (typeof changes.title === 'string') changes.title = changes.title.trim();
    const after = tickets.update(db, id, changes);
    if (after.status !== before.status) {
      await notifier.notify('ticket.status_changed', { id, from: before.status, to: after.status });
    }
    res.json(after);
  });

  return router;
}
