#!/usr/bin/env node
// Lit sur l'entrée standard des lignes « nom|id » (sortie de psql -At -F '|') et écrit { nom: id } en JSON.
let input = '';
for await (const chunk of process.stdin) input += chunk;
const map = Object.fromEntries(
  input.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
    const i = l.lastIndexOf('|');
    return [l.slice(0, i), l.slice(i + 1)];
  }),
);
process.stdout.write(`${JSON.stringify(map, null, 2)}\n`);
