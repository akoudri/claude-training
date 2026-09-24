import { readFileSync } from 'node:fs';
import { basename } from 'node:path';
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
export function importTickets(db, records, { name } = {}) {
  const insert = db.prepare(`INSERT INTO tickets
    (title, description, status, priority, assignee, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)`);

  db.exec('BEGIN');
  try {
    if (name) db.prepare('INSERT INTO imports (name) VALUES (?)').run(name);
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

// Importe un fichier d'historique s'il ne l'a jamais été (suivi dans la table imports).
// Renvoie le nombre de tickets importés, ou null si le fichier avait déjà été importé.
export function importFileOnce(db, file) {
  const name = basename(file);
  if (db.prepare('SELECT 1 FROM imports WHERE name = ?').get(name)) return null;
  return importTickets(db, JSON.parse(readFileSync(file, 'utf8')), { name });
}
