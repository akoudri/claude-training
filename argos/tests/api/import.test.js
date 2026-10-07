import { describe, it, expect } from 'vitest';
import { fileURLToPath } from 'node:url';
import { openDb, migrate } from '../../src/api/db.js';
import { importTickets, importFileOnce } from '../../src/api/import.js';

function freshDb() {
  const db = openDb(':memory:');
  migrate(db);
  return db;
}

describe('importTickets', () => {
  it('normalise la casse des statuts et des priorités', () => {
    const db = freshDb();
    importTickets(db, [
      { title: 'A', status: 'Closed', priority: 'High', createdAt: '2025-11-01T10:00:00Z' },
      { title: 'B', status: ' OPEN ', createdAt: '2025-11-02T10:00:00Z' },
    ]);
    const rows = db.prepare('SELECT status, priority FROM tickets ORDER BY id').all();
    expect(rows.map((r) => ({ ...r }))).toEqual([
      { status: 'closed', priority: 'high' },
      { status: 'open', priority: 'normal' },
    ]);
  });

  it('convertit les dates ISO au format SQLite', () => {
    const db = freshDb();
    importTickets(db, [
      {
        title: 'A',
        status: 'open',
        createdAt: '2025-11-01T10:00:00Z',
        updatedAt: '2025-11-03T08:30:00Z',
      },
    ]);
    const row = db.prepare('SELECT created_at, updated_at FROM tickets').get();
    expect({ ...row }).toEqual({
      created_at: '2025-11-01 10:00:00',
      updated_at: '2025-11-03 08:30:00',
    });
  });

  it('refuse un statut inconnu sans rien importer', () => {
    const db = freshDb();
    expect(() =>
      importTickets(db, [
        { title: 'A', status: 'open', createdAt: '2025-11-01T10:00:00Z' },
        { title: 'B', status: 'wontfix', createdAt: '2025-11-01T10:00:00Z' },
      ]),
    ).toThrow(/wontfix/);
    expect(db.prepare('SELECT count(*) AS n FROM tickets').get().n).toBe(0);
  });
});

describe('importFileOnce', () => {
  const file = fileURLToPath(new URL('../fixtures/historique-extrait.json', import.meta.url));

  it("importe un fichier la première fois, puis l'ignore même si la base a été vidée", () => {
    const db = freshDb();
    expect(importFileOnce(db, file)).toBe(4);

    db.exec('DELETE FROM tickets');

    expect(importFileOnce(db, file)).toBeNull();
    expect(db.prepare('SELECT count(*) AS n FROM tickets').get().n).toBe(0);
  });
});
