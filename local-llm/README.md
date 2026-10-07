# Local LLM

Simple demo

## Tutoriels

Les tutoriels portent sur la stack LLM locale de `docker-compose.yml` (Ollama, Open WebUI, n8n, pgvector). Elle tourne sur toute machine avec Docker : sur le CPU par défaut, ou sur un GPU AMD, Intel ou NVIDIA selon le profil choisi dans `.env` (tutoriel 1, section 2). Les tutoriels sont rangés dans l'ordre conseillé de lecture.

| # | Tutoriel | Contenu |
|---|---|---|
| 1 | [Configurer Open WebUI pour un LLM local](tutorials/01-configuration-open-webui.md) | Contraintes matérielles, profil CPU/GPU, premier démarrage, réglages du modèle, documents et RAG |
| 2 | [Créer un assistant dans le Workspace d'Open WebUI](tutorials/02-assistant-workspace-open-webui.md) | Assistant spécialisé : base de connaissances, outils, partage, mémoire (Notes et Memory) |
| 3 | [Agent de conformité documentaire dans n8n](tutorials/03-agent-n8n.md) | Workflows d'indexation et d'analyse, pseudonymisation, rapport envoyé par mail |
| 4 | [Claude Code dans VS Code avec le LLM local](tutorials/04-claude-code-vscode-local.md) | Brancher Claude Code (CLI et extension) sur Ollama, piège de la fenêtre de contexte |
| 5 | [Isoler l'agent de code : sandbox et dev container](tutorials/05-claude-code-sandbox-devcontainer.md) | Mode sandbox de Claude Code, dev container sur réseau interne derrière une passerelle |
| 6 | [Combiner BMAD et superpowers](tutorials/06-bmad-superpowers.md) | BMAD planifie (spec, stories), superpowers construit chaque story (TDD, revue) |

