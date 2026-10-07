#!/usr/bin/env node
// Hook PreToolUse (Edit|Write|MultiEdit) : interdit de modifier une migration existante.
// Une migration versionnée est considérée comme appliquée, donc immuable ; créer une
// nouvelle migration (ou retoucher une migration pas encore commitée) reste possible.
import { readFileSync, existsSync, readdirSync, realpathSync } from "node:fs";
import { resolve, relative, sep } from "node:path";
import { spawnSync } from "node:child_process";

let input;
try {
  input = JSON.parse(readFileSync(0, "utf8"));
} catch {
  console.error("[protect-migrations] entrée JSON illisible : hook ignoré");
  process.exit(1); // erreur non bloquante
}

const filePath = input?.tool_input?.file_path;
if (!filePath) process.exit(0);

const projectDir = process.env.CLAUDE_PROJECT_DIR ?? input.cwd ?? process.cwd();
const migrationsDir = resolve(projectDir, "migrations");
let target = resolve(input.cwd ?? projectDir, filePath);

// Nouveau fichier : rien à protéger.
if (!existsSync(target)) process.exit(0);

// Chemin canonique (liens symboliques, « .. », casse sous macOS).
target = realpathSync.native(target);
const canonicalDir = existsSync(migrationsDir)
  ? realpathSync.native(migrationsDir)
  : migrationsDir;
if (!target.startsWith(canonicalDir + sep)) process.exit(0);

// Existante mais pas encore versionnée : migration en cours d'écriture, modifiable.
const rel = relative(realpathSync.native(projectDir), target);
const git = spawnSync("git", ["ls-files", "--error-unmatch", "--", rel], {
  cwd: projectDir,
  encoding: "utf8",
});
const gitAvailable = !git.error && !/not a git repository/i.test(git.stderr);
if (gitAvailable && git.status !== 0) process.exit(0);

const numbers = readdirSync(canonicalDir)
  .map((f) => Number.parseInt(f, 10))
  .filter(Number.isFinite);
const next = String(Math.max(0, ...numbers) + 1).padStart(3, "0");

console.error(
  `Modification refusée : ${rel} est une migration existante, considérée comme déjà ` +
    `appliquée. Une migration appliquée ne se modifie jamais : créer plutôt ` +
    `migrations/${next}_<description>.sql pour faire évoluer le schéma.`,
);
process.exit(2);
