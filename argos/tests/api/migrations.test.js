import { describe, it, expect } from 'vitest';
import { copyFileSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { openDb, migrate, MIGRATIONS_DIR } from '../../src/api/db.js';

// Applique les migrations jusqu'à `last` incluse, pour simuler une base créée avant les suivantes.
function migrateUpTo(db, last) {
  const dir = mkdtempSync(join(tmpdir(), 'argos-migrations-'));
  try {
    for (const name of readdirSync(MIGRATIONS_DIR)) {
      if (name.endsWith('.sql') && name <= last) copyFileSync(join(MIGRATIONS_DIR, name), join(dir, name));
    }
    migrate(db, dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

describe('migrations', () => {
  it("s'appliquent dans l'ordre sur une base vide", () => {
    const db = openDb(':memory:');
    const applied = migrate(db);
    expect(applied[0]).toBe('001_create_tickets.sql');
    expect(applied).toEqual([...applied].sort());
  });

  it('ne sont pas rejouées une seconde fois', () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(migrate(db)).toEqual([]);
  });
});

describe('003 — normalisation des tickets', () => {
  it('corrige les valeurs et les dates déjà importées', () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '002_add_assignee.sql');
    db.prepare(
      `INSERT INTO tickets (title, status, priority, created_at, updated_at)
       VALUES ('A', 'Closed', 'High', '2025-11-01T10:00:00Z', '2025-11-02T10:00:00Z')`,
    ).run();

    migrate(db);

    const row = db.prepare('SELECT id, status, priority, created_at, updated_at FROM tickets').get();
    expect({ ...row }).toEqual({
      id: 1,
      status: 'closed',
      priority: 'high',
      created_at: '2025-11-01 10:00:00',
      updated_at: '2025-11-02 10:00:00',
    });
  });

  it('ne réattribue pas le numéro d’un ticket supprimé', () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '002_add_assignee.sql');
    db.exec("INSERT INTO tickets (title) VALUES ('A'), ('B'), ('C')");
    db.exec('DELETE FROM tickets WHERE id = 3');

    migrate(db);
    const { lastInsertRowid } = db.prepare("INSERT INTO tickets (title) VALUES ('D')").run();

    expect(Number(lastInsertRowid)).toBe(4);
  });

  it('refuse un statut ou une priorité hors liste', () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(() => db.prepare("INSERT INTO tickets (title, status) VALUES ('A', 'Closed')").run()).toThrow(/CHECK/);
    expect(() => db.prepare("INSERT INTO tickets (title, priority) VALUES ('A', 'urgent')").run()).toThrow(/CHECK/);
  });
});

describe('004 — suivi des imports', () => {
  it("considère l'historique comme déjà importé sur une base qui contient des tickets", () => {
    const db = openDb(':memory:');
    migrateUpTo(db, '003_normalize_tickets.sql');
    db.exec("INSERT INTO tickets (title) VALUES ('A')");

    migrate(db);

    expect(db.prepare('SELECT name FROM imports').all().map((r) => r.name)).toEqual(['historique.json']);
  });

  it('ne marque rien sur une base neuve', () => {
    const db = openDb(':memory:');
    migrate(db);
    expect(db.prepare('SELECT count(*) AS n FROM imports').get().n).toBe(0);
  });
});
