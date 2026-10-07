import { defineConfig } from 'vitest/config';

// Tests de performance, hors de `npm test` : leurs durées dépendent de la machine.
//   npm run test:perf   budgets de temps (échec si dépassés)
//   npm run bench       mesures sans seuil (vitest bench)
export default defineConfig({
  test: {
    include: ['tests/perf/**/*.perf.js'],
    benchmark: { include: ['tests/perf/**/*.bench.js'] },
    environment: 'node',
    // Un seul fichier à la fois : les mesures ne se disputent pas le processeur.
    fileParallelism: false,
  },
});
