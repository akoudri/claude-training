import { normalize } from '../text.js';

export const STATUSES = ['open', 'in_progress', 'closed'];
export const PRIORITIES = ['low', 'normal', 'high'];

// Filtres de liste : open = non clos (ouverts ou en cours), closed = clos, sinon tout.
const STATUS_FILTERS = {
  open: "status <> 'closed'",
  closed: "status = 'closed'",
};

export function findAll(db, { status = 'all', q = '' } = {}) {
  const conditions = [];
  const params = [];
  if (Object.hasOwn(STATUS_FILTERS, status)) conditions.push(STATUS_FILTERS[status]);
  // Recherche dans le titre ou la description, sans tenir compte de la casse ni des accents.
  // instr plutôt que LIKE : sous-chaîne exacte, sans jokers % et _ à échapper.
  const keyword = normalize(q.trim());
  if (keyword) {
    conditions.push('(instr(normalize(title), ?) > 0 OR instr(normalize(description), ?) > 0)');
    params.push(keyword, keyword);
  }
  const where = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
  return db.prepare(`SELECT * FROM tickets ${where} ORDER BY id`).all(...params);
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
