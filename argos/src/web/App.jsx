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
  const [query, setQuery] = useState('');
  const [tickets, setTickets] = useState([]);
  const [stats, setStats] = useState(null);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState(null);

  const [version, setVersion] = useState(0);
  const refresh = () => setVersion((v) => v + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listTickets(filter, query), api.getStats()])
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
  }, [filter, query, version]);

  // Le détail reste affiché même si le ticket sort du filtre courant (par exemple clos sous « Ouverts »).
  const select = (id) => setSelected(tickets.find((t) => t.id === id) ?? null);
  const handleUpdated = (ticket) => {
    setSelected(ticket);
    refresh();
  };

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
        <input
          type="search"
          aria-label="Rechercher"
          placeholder="Rechercher…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </nav>

      <main>
        <section>
          <TicketList
            tickets={tickets}
            selectedId={selected?.id ?? null}
            onSelect={select}
            emptyMessage={query.trim() ? `Aucun ticket ne correspond à « ${query.trim()} ».` : undefined}
          />
          <NewTicketForm onCreated={refresh} />
        </section>
        <aside>
          {selected ? (
            <TicketDetail key={selected.id} ticket={selected} onUpdated={handleUpdated} />
          ) : (
            <p className="hint">Sélectionner un ticket pour afficher son détail.</p>
          )}
        </aside>
      </main>
    </div>
  );
}
