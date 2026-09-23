import { useState } from 'react';
import { api } from '../api.js';
import { PRIORITY_LABELS } from '../labels.js';

export default function NewTicketForm({ onCreated }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('normal');
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    try {
      await api.createTicket({ title, description, priority });
      setTitle('');
      setDescription('');
      setPriority('normal');
      setError(null);
      onCreated();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <form className="new-ticket" onSubmit={submit}>
      <h3>Nouveau ticket</h3>
      <input placeholder="Titre" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea
        placeholder="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />
      <select value={priority} onChange={(e) => setPriority(e.target.value)}>
        {Object.entries(PRIORITY_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <button type="submit">Créer</button>
      {error && <p className="error">{error}</p>}
    </form>
  );
}
