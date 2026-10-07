export const STATUSES = ['open', 'in_progress', 'closed'];
export const PRIORITIES = ['low', 'normal', 'high'];

// Filtres de liste : open = non clos (ouverts ou en cours), closed = clos, sinon tout.
const STATUS_FILTERS = {
  open: "WHERE status <> 'closed'",
  closed: "WHERE status = 'closed'",
};

export function findAll(db, { status = 'all' } = {}) {
  const where = Object.hasOwn(STATUS_FILTERS, status) ? STATUS_FILTERS[status] : '';
  return db.prepare(`SELECT * FROM tickets ${where} ORDER BY id`).all();
}

// Compteurs affichés dans l'en-tête de l'interface.
export function countByStatus(db) {
  const counts = { total: 0 };
  for (const status of STATUSES) counts[status] = 0;
  for (const { status, n } of db.prepare('SELECT status, count(*) AS n FROM tickets GROUP BY status').all()) {
    counts[status] = n;
    counts.total += n;
  }
  return counts;
}

export function findById(db, id) {
  return db.prepare('SELECT * FROM tickets WHERE id = ?').get(id);
}

export function create(db, { title, description = '', priority = 'normal', assignee = null }) {
  const { lastInsertRowid } = db
    .prepare('INSERT INTO tickets (title, description, priority, assignee) VALUES (?, ?, ?, ?)')
    .run(title, description, priority, assignee);
  return findById(db, lastInsertRowid);
}

const UPDATABLE = ['title', 'description', 'status', 'priority', 'assignee'];

export function update(db, id, changes) {
  const fields = UPDATABLE.filter((f) => changes[f] !== undefined);
  if (fields.length > 0) {
    const set = fields.map((f) => `${f} = ?`).join(', ');
    db.prepare(`UPDATE tickets SET ${set}, updated_at = datetime('now') WHERE id = ?`).run(
      ...fields.map((f) => changes[f]),
      id,
    );
  }
  return findById(db, id);
}
