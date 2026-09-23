import { useState } from 'react';
import { api } from '../api.js';
import { STATUS_LABELS, PRIORITY_LABELS } from '../labels.js';

export default function TicketDetail({ ticket, onUpdated }) {
  const [error, setError] = useState(null);

  async function changeStatus(status) {
    try {
      await api.updateTicket(ticket.id, { status });
      setError(null);
      onUpdated();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <article className="detail">
      <h2>
        #{ticket.id} — {ticket.title}
      </h2>
      <p className="meta">
        Priorité {PRIORITY_LABELS[ticket.priority] ?? ticket.priority} · Responsable{' '}
        {ticket.assignee ?? 'non attribué'} · Créé le {ticket.created_at.slice(0, 10)}
      </p>
      <p>{ticket.description || <em>Pas de description.</em>}</p>

      <label>
        Statut{' '}
        <select value={ticket.status} onChange={(e) => changeStatus(e.target.value)}>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      {error && <p className="error">{error}</p>}
    </article>
  );
}
