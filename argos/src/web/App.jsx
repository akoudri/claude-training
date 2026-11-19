import { useEffect, useState } from 'react';
import { api } from './api.js';
import StatsBar from './components/StatsBar.jsx';
import TicketList from './components/TicketList.jsx';
import TicketDetail from './components/TicketDetail.jsx';
import NewTicketForm from './components/NewTicketForm.jsx';

const FILTERS = [
  { value: 'open', label: 'Ouverts' },
  { value: 'closed', label: 'Clos' },
  { value: 'all', label: 'Tous' },
];

export default function App() {
  const [filter, setFilter] = useState('open');
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState(null);

  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listTickets(filter), api.getStats()])
      .then(([list, counts]) => {
        if (cancelled) return;
        setTickets(list);
        setStats(counts);
        setError(null);
      })
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [filter, version]);

  const selected = tickets.find((t) => t.id === selectedId) ?? null;

  return (
    <div className="app">
      <header>
        <h1>Argos</h1>
        <StatsBar stats={stats} />
      </header>

      {error && <p className="error">Erreur : {error}</p>}

      <nav className="filters">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={f.value === filter ? 'active' : ''}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </nav>

      <main>
        <section>
          <TicketList tickets={tickets} selectedId={selectedId} onSelect={setSelectedId} />
          <NewTicketForm onCreated={refresh} />
        </section>
        <aside>
          {selected ? (
            <TicketDetail ticket={selected} onUpdated={refresh} />
          ) : (
            <p className="hint">Sélectionner un ticket pour afficher son détail.</p>
          )}
        </aside>
      </main>
    </div>
  );
}
