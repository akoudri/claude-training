// Lance l'API (port 3000) et l'interface Vite (port 5173) en parallèle.
import { spawn } from 'node:child_process';

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const children = ['dev:api', 'dev:web'].map((script) =>
  spawn(npm, ['run', '--silent', script], { stdio: 'inherit', shell: process.platform === 'win32' }),
);

const stop = () => children.forEach((c) => c.kill());
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
children.forEach((c) => c.on('exit', (code) => code && stop()));
