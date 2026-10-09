# Local LLM

Stack LLM locale pour la formation : Ollama (CPU ou GPU), Open WebUI avec RAG dans pgvector, et, en option, n8n (agent de conformité du tutoriel 3) et Docling (meilleure lecture des PDF). Tout tourne sur la machine : aucun document ni aucune requête ne part sur Internet.

| Service | Rôle | Accès |
|---|---|---|
| `ollama` | Inférence (modèle de chat et modèle d'embedding) | http://localhost:11434 |
| `ollama-init` | Télécharge les modèles de `.env`, puis s'arrête | — |
| `postgres` | Base de n8n et base `rag` (pgvector) | `localhost:5433` |
| `open-webui` | Chat et bases de connaissances | http://localhost:3000 |
| `open-webui-init` | Applique les réglages du tutoriel 1 (`open-webui/configurer.py`), puis s'arrête | — |
| `ollama-gateway` | Passerelle des dev containers vers Ollama (tutoriel 5) | réseau `llm-agents` |
| `n8n` (option) | Agent de conformité documentaire | http://localhost:5678 |
| `docling` (option) | Conversion des PDF, DOCX, PPTX et XLSX en Markdown | interne |

Tous les ports sont publiés sur `127.0.0.1` uniquement.

## Déployer depuis zéro

Les commandes se lancent depuis le dossier `local-llm/`. Le détail de chaque étape est dans le [tutoriel 1](tutorials/01-configuration-open-webui.md), section 2.

### Prérequis

- Docker avec Compose v2 (Linux, macOS, ou WSL2 sous Windows) ;
- de l'espace disque : ~6,5 Go pour les modèles, ~5 Go pour l'image de Docling, plus les autres images ;
- ~8 Go de mémoire libre pour `granite4.2:8b` avec un contexte de 32k, en mémoire GPU ou en RAM ;
- pour n8n seulement : Node.js 22 ou plus récent sur l'hôte.

### 1. Effacer une installation existante

À sauter sur une machine neuve. Garder une copie de `.env` si ses réglages doivent être réutilisés, puis :

```bash
docker compose down --remove-orphans
docker volume rm local-llm_openwebui local-llm_pg local-llm_n8n   # comptes, conversations, bases, workflows : perdus
docker volume rm local-llm_ollama                                 # facultatif : évite de retélécharger ~6,5 Go de modèles
docker compose pull                                               # dernières images (Open WebUI suit la branche main) ; "denied" sur ghcr.io : docker logout ghcr.io
```

Supprimer le volume `local-llm_openwebui` est indispensable pour repartir des réglages de `docker-compose.yml` : Open WebUI ne lit ses variables d'environnement qu'au premier démarrage (PersistentConfig).

### 2. Créer `.env`

```bash
cp .env.example .env
for v in POSTGRES_PASSWORD N8N_ENCRYPTION_KEY WEBUI_SECRET_KEY WEBUI_ADMIN_PASSWORD; do
  sed -i "s/^$v=change-me$/$v=$(openssl rand -hex 32)/" .env      # sous macOS : sed -i ''
done
grep WEBUI_ADMIN_ .env                                            # identifiants de connexion à Open WebUI
```

Puis éditer `.env` :

| Variable | À régler |
|---|---|
| `COMPOSE_FILE` | Décommenter **une** ligne selon la machine (aucune : CPU seul). Ajouter `:docker-compose.n8n.yml` pour n8n et `:docker-compose.docling.yml` pour Docling, par exemple `COMPOSE_FILE=docker-compose.yml:docker-compose.vulkan.yml:docker-compose.n8n.yml:docker-compose.docling.yml`. |
| `RENDER_GID`, `VIDEO_GID` | Profil vulkan seulement : valeurs de `getent group render video`. |
| `WEBUI_ADMIN_EMAIL` | Adresse du compte administrateur. Vide : `open-webui-init` ne configure rien et tout se règle à la main. |
| `OPENWEBUI_EXEMPLES` | `true` pour créer la base `MBSE Expert` et l'assistant `Expert MBSE` des tutoriels 1 et 2. |
| `OLLAMA_CONTEXT_LENGTH`, `LLM_MODEL`, `OLLAMA_MEM_LIMIT` | À réduire sur une machine modeste (tutoriel 1, section 2). |

### 3. Démarrer et vérifier

```bash
docker compose up -d
docker compose logs -f ollama-init        # téléchargement des modèles ; se termine par "success"
docker compose ps -a                      # ollama-init et open-webui-init : "Exited (0)" ; docling : "(healthy)"
docker compose logs open-webui-init       # "modèle de base granite4.2:8b : réglé", et "Docling" avec l'overlay
```

Ouvrir http://localhost:3000 et se connecter avec `WEBUI_ADMIN_EMAIL` / `WEBUI_ADMIN_PASSWORD`. Après un premier message, `docker compose exec ollama ollama ps` doit afficher `100% GPU` avec un profil GPU.

Avec Docling, les PDF déposés dans une base de connaissances comme ceux joints à une conversation passent par Docling. La recherche dans les extraits est décrite au tutoriel 1, sections 5 à 7.

### 4. n8n (option, tutoriel 3)

1. Ouvrir http://localhost:5678 et créer le compte propriétaire.
2. Créer les trois identifiants, **avec ces noms exacts** : `Ollama local`, `Postgres rag`, `Gmail SMTP` (tutoriel 3, section 3.2).
3. Créer les fichiers de configuration, puis les remplir :

   ```bash
   cp -n n8n/config/notification.example.json n8n/config/notification.json
   cp -n n8n/config/sensitive-terms.example.json n8n/config/sensitive-terms.json
   ```

   `cp -n` garde les fichiers déjà remplis lors d'une installation précédente : ils sont hors des volumes Docker.

4. Tester et déployer les workflows :

   ```bash
   node --test "n8n/test/**/*.test.*"
   bash n8n/scripts/deploy.sh
   ```

5. Indexer le corpus fictif : tutoriel 3, section 5.1.

### Désactiver une option

Retirer l'overlay de `COMPOSE_FILE`, puis `docker compose up -d --remove-orphans`. Pour Docling, `open-webui-init` remet alors l'extracteur intégré d'Open WebUI.

## Tutoriels

Les tutoriels portent sur la stack LLM locale de `docker-compose.yml` (Ollama, Open WebUI, pgvector), complétée au besoin par n8n (`docker-compose.n8n.yml`, requis par le tutoriel 3) et par Docling (`docker-compose.docling.yml`, meilleure lecture des PDF par Open WebUI, tutoriel 1, section 6.2.1). Elle tourne sur toute machine avec Docker : sur le CPU par défaut, ou sur un GPU AMD, Intel ou NVIDIA selon le profil choisi dans `.env` (tutoriel 1, section 2). Les tutoriels sont rangés dans l'ordre conseillé de lecture.

| # | Tutoriel | Contenu |
|---|---|---|
| 1 | [Configurer Open WebUI pour un LLM local](tutorials/01-configuration-open-webui.md) | Contraintes matérielles, profil CPU/GPU, premier démarrage, réglages du modèle, documents et RAG |
| 2 | [Créer un assistant dans le Workspace d'Open WebUI](tutorials/02-assistant-workspace-open-webui.md) | Assistant spécialisé : base de connaissances, outils, partage, mémoire (Notes et Memory) |
| 3 | [Agent de conformité documentaire dans n8n](tutorials/03-agent-n8n.md) | Workflows d'indexation et d'analyse, pseudonymisation, rapport envoyé par mail |
| 4 | [Claude Code dans VS Code avec le LLM local](tutorials/04-claude-code-vscode-local.md) | Brancher Claude Code (CLI et extension) sur Ollama, piège de la fenêtre de contexte |
| 5 | [Isoler l'agent de code : sandbox et dev container](tutorials/05-claude-code-sandbox-devcontainer.md) | Mode sandbox de Claude Code, dev container sur réseau interne derrière une passerelle |
| 6 | [Combiner BMAD et superpowers](tutorials/06-bmad-superpowers.md) | BMAD planifie (spec, stories), superpowers construit chaque story (TDD, revue) |
