-- 004 — Suivi des imports réalisés : l'historique n'est importé qu'une fois, même si la base se vide.
CREATE TABLE imports (
  name        TEXT PRIMARY KEY,
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les bases existantes ont déjà reçu l'historique lors de leur premier démarrage.
INSERT INTO imports (name) SELECT 'historique.json' WHERE EXISTS (SELECT 1 FROM tickets);
