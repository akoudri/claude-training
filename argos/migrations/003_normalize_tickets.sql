-- 003 — Normalisation des données importées et contraintes sur les valeurs autorisées
UPDATE tickets SET status = lower(trim(status)), priority = lower(trim(priority));
UPDATE tickets SET created_at = replace(substr(created_at, 1, 19), 'T', ' ')
  WHERE created_at LIKE '____-__-__T%';
UPDATE tickets SET updated_at = replace(substr(updated_at, 1, 19), 'T', ' ')
  WHERE updated_at LIKE '____-__-__T%';

-- SQLite ne sait pas ajouter une contrainte CHECK à une table existante : on la reconstruit.
CREATE TABLE tickets_new (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  title       TEXT    NOT NULL,
  description TEXT    NOT NULL DEFAULT '',
  status      TEXT    NOT NULL DEFAULT 'open'   CHECK (status IN ('open', 'in_progress', 'closed')),
  priority    TEXT    NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  assignee    TEXT
);
INSERT INTO tickets_new (id, title, description, status, priority, created_at, updated_at, assignee)
  SELECT id, title, description, status, priority, created_at, updated_at, assignee FROM tickets;

-- Conserve le compteur AUTOINCREMENT : un numéro de ticket supprimé ne doit pas être réattribué.
DELETE FROM sqlite_sequence WHERE name = 'tickets_new';
INSERT INTO sqlite_sequence (name, seq) SELECT 'tickets_new', seq FROM sqlite_sequence WHERE name = 'tickets';

DROP TABLE tickets;
ALTER TABLE tickets_new RENAME TO tickets;
