export const STATUSES = ['open', 'in_progress', 'closed'];
export const PRIORITIES = ['low', 'normal', 'high'];

export function findAll(db) {
  return db.prepare('SELECT * FROM tickets ORDER BY id').all();
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
