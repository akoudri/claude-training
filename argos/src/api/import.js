import { readFileSync } from 'node:fs';
import { STATUSES, PRIORITIES } from './repositories/tickets.js';

// L'ancien outil n'imposait pas la casse ('Closed', 'CLOSED', 'High'…) : chaque valeur est
// ramenée à sa forme canonique, et une valeur inconnue interrompt l'import.
function canonical(value, allowed, fallback, label, index) {
  const normalized = String(value ?? fallback).trim().toLowerCase();
  if (!allowed.includes(normalized)) {
    throw new Error(`Ticket ${index + 1} : ${label} inconnu « ${value} »`);
  }
  return normalized;
}

// '2025-11-03T09:12:00Z' → '2025-11-03 09:12:00', le format de datetime('now') dans SQLite.
function sqliteDate(iso, index) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) throw new Error(`Ticket ${index + 1} : date invalide « ${iso} »`);
  return date.toISOString().slice(0, 19).replace('T', ' ');
}

// Import de l'historique des tickets (export de l'ancien outil de support).
export function importTickets(db, records) {
  const insert = db.prepare(`INSERT INTO tickets
    (title, description, status, priority, assignee, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)`);

  db.exec('BEGIN');
  try {
    records.forEach((r, i) => {
      insert.run(
        r.title,
        r.description ?? '',
        canonical(r.status, STATUSES, 'open', 'statut', i),
        canonical(r.priority, PRIORITIES, 'normal', 'priorité', i),
        r.assignee ?? null,
        sqliteDate(r.createdAt, i),
        sqliteDate(r.updatedAt ?? r.createdAt, i),
      );
    });
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
