import { STATUS_LABELS, PRIORITY_LABELS } from '../labels.js';

export default function TicketList({ tickets, selectedId, onSelect }) {
  if (tickets.length === 0) return <p className="hint">Aucun ticket.</p>;

  return (
    <ul className="tickets">
      {tickets.map((ticket) => (
        <li
          key={ticket.id}
          className={[
            ticket.status === 'closed' ? 'closed' : '',
            ticket.id === selectedId ? 'selected' : '',
          ].join(' ')}
        >
          <button
            type="button"
            className="ticket"
            aria-current={ticket.id === selectedId ? 'true' : undefined}
            onClick={() => onSelect(ticket.id)}
          >
            <span className="id">#{ticket.id}</span>
            <span className="title">{ticket.title}</span>
            <span className={`badge priority-${ticket.priority}`}>
              {PRIORITY_LABELS[ticket.priority] ?? ticket.priority}
            </span>
            <span className="status">{STATUS_LABELS[ticket.status] ?? ticket.status}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
