import { performance } from 'node:perf_hooks';

// Durée médiane (ms) de `runs` exécutions après `warmup` exécutions de chauffe :
// la médiane écarte les pics ponctuels (ramasse-miettes, machine chargée).
export async function median(fn, { warmup = 2, runs = 7 } = {}) {
  for (let i = 0; i < warmup; i++) await fn();
  const times = [];
  for (let i = 0; i < runs; i++) {
    const start = performance.now();
    await fn();
    times.push(performance.now() - start);
  }
  times.sort((a, b) => a - b);
  return times[Math.floor(times.length / 2)];
}
