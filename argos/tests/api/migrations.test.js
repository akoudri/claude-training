import { describe, it, expect } from 'vitest';
import { openDb, migrate } from '../../src/api/db.js';

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
