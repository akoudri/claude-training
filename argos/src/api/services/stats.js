import { STATUSES } from '../repositories/tickets.js';

// Compteurs affichés dans l'en-tête de l'interface.
export function countByStatus(tickets) {
  const counts = { total: tickets.length };
  for (const status of STATUSES) {
    counts[status] = tickets.filter((t) => t.status === status).length;
  }
  return counts;
}
