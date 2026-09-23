// Charge .env s'il existe. Importé en premier par server.js, avant tout module qui lit
// process.env au chargement.
import { existsSync } from 'node:fs';

if (existsSync('.env')) process.loadEnvFile('.env');
