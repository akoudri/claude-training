// Chemins absolus du projet : l'API et les scripts fonctionnent quel que soit le répertoire courant.
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT_DIR = fileURLToPath(new URL('../../', import.meta.url));
export const ENV_FILE = join(ROOT_DIR, '.env');
export const DIST_DIR = join(ROOT_DIR, 'dist');
export const HISTORY_FILE = join(ROOT_DIR, 'data/historique.json');
export const MIGRATIONS_DIR = join(ROOT_DIR, 'migrations');
