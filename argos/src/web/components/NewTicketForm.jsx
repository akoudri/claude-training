import { useState } from 'react';
import { api } from '../api.js';
import { PRIORITY_LABELS } from '../labels.js';

export default function NewTicketForm({ onCreated }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('normal');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      await api.createTicket({ title, description, priority });
      setTitle('');
      setDescription('');
      setPriority('normal');
      setError(null);
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="new-ticket" onSubmit={submit}>
      <h3>Nouveau ticket</h3>
      <label htmlFor="new-ticket-title">Titre</label>
      <input id="new-ticket-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <label htmlFor="new-ticket-description">Description</label>
      <textarea
        id="new-ticket-description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <label htmlFor="new-ticket-priority">Priorité</label>
      <select id="new-ticket-priority" value={priority} onChange={(e) => setPriority(e.target.value)}>
        {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <button type="submit" disabled={submitting}>
        Créer
      </button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
