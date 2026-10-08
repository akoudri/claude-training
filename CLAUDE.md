# Formation Claude Code — Janus Academy

Dépôt du formateur : support, labs et démos de la formation Claude Code (6 modules, M1 à M6).
Tout le contenu est rédigé en français.

## Contenu

- `Formation Claude.pdf` : support de cours.
- `labs/` : énoncés des labs M1 à M6 et `README.md` pour les apprenants.
- `argos/` : application fil rouge (Node 22.13+, Express, `node:sqlite`, React/Vite, Vitest), dans une version avancée
  (avec son propre `argos/CLAUDE.md`, qui fait foi pour le code d'Argos). Ce n'est pas l'état de départ des labs :
  les apprenants clonent un dépôt Argos séparé, sans `CLAUDE.md`, que le lab M2 leur fait créer.
- `argos-marketplace/` : marketplace de démonstration (plugin `argos-toolkit@janus-argos`), extension du lab M2.
- `mcp/` : démos de serveurs MCP en Python (uv). `server.py` (bloc-notes NotesRapides), `blender_mcp_server.py` + `blender_server.py` (pont Claude Code → Blender, TCP 9876).
- `obfuscation/` : outil Python (uv) d'obfuscation réversible de documents Word, Excel, PowerPoint et PDF par dictionnaires, avant envoi à Claude (`obfusquer` / `restaurer`, et `detecter` qui propose un dictionnaire candidat à l'aide de l'Ollama de `local-llm/`).
- `local-llm/` : stack LLM locale (Ollama sur CPU, ou sur GPU via `docker-compose.vulkan.yml` / `docker-compose.nvidia.yml` choisis par `COMPOSE_FILE` dans `.env` ; Open WebUI, pgvector, passerelle nginx ; n8n optionnel via `docker-compose.n8n.yml`, ajouté à `COMPOSE_FILE`) avec 6 tutoriels dans `tutorials/` et un agent de conformité n8n dans `n8n/`.
- `local/` : matériel formateur (guide, bundles Argos, labs originaux, script de correction du support). Exclu de git.

## Commandes

- Argos : `cd argos && npm install && npm test` (budgets de performance : `npm run perf`)
- Agent n8n : `cd local-llm && node --test 'n8n/test/*.test.*'` ; build des workflows : `node n8n/scripts/build.mjs` ; déploiement : `n8n/scripts/deploy.sh`
- MCP : `cd mcp && uv sync`
- Obfuscation : `cd obfuscation && uv sync && uv run pytest`

## Règles

- Ne jamais versionner de secrets ni de données locales : `local-llm/.env`, `local-llm/n8n/config/*` (seuls les `*.example.json` sont suivis), `local-llm/documents/`, `local-llm/reports/`, `mcp/notes.json`, les tables de correspondance `*.table.json`, les dictionnaires candidats `*.candidats.yaml`, `obfuscation/exemples/generes/`. Vérifier le `.gitignore` à chaque nouvel ajout.
- Les workflows de `local-llm/n8n/workflows/` sont générés par `build.mjs` à partir de `n8n/src/` : modifier les sources, pas le JSON. Ils ne doivent contenir aucun identifiant d'instance n8n.
- Pas de chemins absolus propres à la machine dans les README et les tutoriels. Les tutoriels doivent fonctionner sur toute machine : une durée ou un débit mesuré est attribué à la « configuration de référence » (Ryzen 7 7840HS, iGPU Radeon 780M, profil vulkan).
- Garder labs, support, errata et état d'Argos cohérents entre eux.
- Commits au format Conventional Commits.
