import { readFileSync } from 'node:fs';

// Import de l'historique des tickets (export de l'ancien outil de support).
export function importTickets(db, records) {
  const insert = db.prepare(`INSERT INTO tickets
    (title, description, status, priority, assignee, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)`);

  db.exec('BEGIN');
  try {
    for (const r of records) {
      insert.run(
        r.title,
        r.description ?? '',
        r.status,
        r.priority ?? 'normal',
        r.assignee ?? null,
        r.createdAt,
        r.updatedAt ?? r.createdAt,
      );
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  }
  return records.length;
}

export function importFile(db, file) {
  return importTickets(db, JSON.parse(readFileSync(file, 'utf8')));
}
