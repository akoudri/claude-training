// Charge .env s'il existe. Importé en premier par server.js et les scripts, avant tout module qui
// lit process.env au chargement.
import { existsSync } from 'node:fs';
import { ENV_FILE } from './paths.js';

if (existsSync(ENV_FILE)) process.loadEnvFile(ENV_FILE);
