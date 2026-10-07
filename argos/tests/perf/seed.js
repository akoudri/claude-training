import { setup } from '../helpers.js';
import { STATUSES, PRIORITIES } from '../../src/api/repositories/tickets.js';

// Enregistrements au format de l'ancien outil, répartis sur tous les statuts et priorités.
export function makeRecords(n) {
  return Array.from({ length: n }, (_, i) => ({
    title: `Ticket de charge n° ${i + 1}`,
    description: 'Description de test '.repeat(10),
    status: STATUSES[i % STATUSES.length],
    priority: PRIORITIES[i % PRIORITIES.length],
    assignee: i % 4 === 0 ? null : `agent-${i % 25}`,
    createdAt: new Date(Date.UTC(2025, 0, 1) + i * 60_000).toISOString(),
  }));
}

// Base en mémoire migrée contenant n tickets, avec l'application prête à tester.
export function setupWithTickets(n) {
  const ctx = setup({ fixture: null });
  ctx.db.exec('BEGIN');
  const insert = ctx.db.prepare(
    'INSERT INTO tickets (title, description, status, priority, assignee) VALUES (?, ?, ?, ?, ?)',
  );
  for (const r of makeRecords(n)) insert.run(r.title, r.description, r.status, r.priority, r.assignee);
  ctx.db.exec('COMMIT');
  return ctx;
}
