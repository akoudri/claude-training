import { DatabaseSync } from 'node:sqlite';
import { mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const MIGRATIONS_DIR = join(dirname(fileURLToPath(import.meta.url)), '../../migrations');
export const DEFAULT_DB_FILE = process.env.ARGOS_DB ?? 'data/argos.db';

export function openDb(file = DEFAULT_DB_FILE) {
  if (file !== ':memory:') mkdirSync(dirname(file), { recursive: true });
  const db = new DatabaseSync(file);
  db.exec('PRAGMA foreign_keys = ON');
  return db;
}

// Applique, dans l'ordre, les migrations SQL qui ne l'ont pas encore été.
export function migrate(db, dir = MIGRATIONS_DIR) {
  db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
  )`);
  const applied = new Set(db.prepare('SELECT name FROM schema_migrations').all().map((r) => r.name));
  const pending = readdirSync(dir)
    .filter((f) => f.endsWith('.sql') && !applied.has(f))
    .sort();

  for (const name of pending) {
    db.exec('BEGIN');
    try {
      db.exec(readFileSync(join(dir, name), 'utf8'));
      db.prepare('INSERT INTO schema_migrations (name) VALUES (?)').run(name);
      db.exec('COMMIT');
    } catch (err) {
      db.exec('ROLLBACK');
      throw new Error(`Migration ${name} en échec : ${err.message}`, { cause: err });
    }
  }
  return pending;
}
