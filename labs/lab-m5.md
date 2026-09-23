# Lab M5 — Reproduire Argos

## Contexte

Argos est corrigé, configuré, coordonné en multi-agents et durci depuis les labs précédents,
mais tout cela ne vit encore que sur un seul poste. Ce lab transforme cette configuration en un
environnement versionné, capable de se reproduire à l'identique ailleurs.

## Prérequis

- Argos avec le sandbox et l'allowlist réseau du lab M4 en place.
- Docker installé localement, et VS Code avec l'extension Dev Containers (ou la CLI
  `@devcontainers/cli`) pour la partie devcontainer.
- Un compte GitHub avec accès à Codespaces pour la partie Codespace, et le dépôt Argos poussé sur
  GitHub (Codespaces et Claude Code on the web partent d'un dépôt GitHub).

## SOCLE — pour tous

1. **Écrire le devcontainer d'Argos**
   Créer `.devcontainer/devcontainer.json` avec une image de base adaptée au projet (même version
   majeure de Node que `.nvmrc`, par exemple
   `mcr.microsoft.com/devcontainers/javascript-node:22-bookworm`) et Claude Code installé par la
   feature officielle `ghcr.io/anthropics/devcontainer-features/claude-code:1.0`.
   - [ ] Le conteneur se construit sans erreur.
   - [ ] Claude Code est disponible dès l'ouverture, sans installation manuelle supplémentaire.

2. **Faire persister l'authentification**
   Ajouter un volume nommé monté sur `/home/node/.claude` **et** la variable
   `"containerEnv": { "CLAUDE_CONFIG_DIR": "/home/node/.claude" }` : sans elle, le fichier
   `~/.claude.json`, qui porte le compte connecté, reste hors du volume et se perd au rebuild.
   - [ ] Une reconstruction volontaire du conteneur (rebuild) ne redemande pas
     d'authentification.

3. **Vérifier ce qui suit de M4, et ce qui ne suit pas**
   Le `.claude/settings.json` versionné arrive tel quel dans le conteneur : règles de permission
   et hook s'appliquent. Le sandbox Bash, lui, ne peut pas démarrer dans un conteneur Docker
   standard (pas de namespaces utilisateur) : Claude Code le signale et exécute les commandes sans
   sandbox. Dans un devcontainer, c'est le conteneur qui isole le système de fichiers, et
   l'allowlist réseau se reporte sur un pare-feu sortant lancé au démarrage du conteneur
   (`postStartCommand`, capacités `NET_ADMIN` et `NET_RAW`), sur le modèle du script
   `init-firewall.sh` du devcontainer de référence d'Anthropic.
   - [ ] Une tentative de modification d'une migration existante est refusée par le hook, comme en
     local, et la lecture de `.env` par la règle de permission.
   - [ ] `/sandbox` (ou l'avertissement au démarrage) montre que le sandbox n'est pas actif dans
     le conteneur : le constater plutôt que le supposer.
   - [ ] Depuis le conteneur, `curl https://example.com` échoue alors que
     `npm view vitest version` fonctionne.

4. **Ouvrir Argos dans un Codespace**
   À partir du même dépôt, lancer un Codespace et vérifier que Claude Code y est immédiatement
   opérationnel.
   - [ ] Le Codespace démarre avec le même environnement que le devcontainer local, sans
     configuration supplémentaire.
   - [ ] La suite de tests passe de façon identique dans les deux environnements.

## EXTENSION — pour aller plus loin

- Suivre depuis le navigateur une session lancée dans le terminal du Codespace : `/remote-control`
  rend la session locale pilotable depuis claude.ai ou l'application mobile. Autre voie :
  `claude --cloud "<tâche>"` crée une nouvelle session dans le cloud (claude.ai/code), que
  `claude --teleport` rapatrie ensuite dans le terminal avec son historique. Une session de
  terminal existante ne se transfère pas telle quelle vers le web.
- Comparer le temps de démarrage et l'expérience d'usage entre le devcontainer local et le
  Codespace, et noter dans CLAUDE.md lequel privilégier selon la situation.
- Faire évaluer par l'agent si l'image de base choisie pour le devcontainer pourrait être allégée
  sans perdre en fonctionnalité.

## Pièges & indices

- Une version d'image de base différente de celle utilisée jusqu'ici en local peut faire échouer
  silencieusement un test qui dépendait d'un comportement spécifique à une version : vérifier la
  version exacte plutôt que de prendre la dernière disponible par défaut.
- Un rebuild qui semble réussir mais redemande une authentification signale presque toujours un
  volume mal déclaré ou mal monté.
- Un sandbox ou une allowlist qui semblent fonctionner par défaut dans un nouvel environnement
  n'ont pas forcément été réellement appliqués : toujours vérifier par un essai de contournement,
  pas seulement par l'absence d'erreur. C'est précisément le cas du sandbox Bash dans un
  conteneur.
- Un volume nommé est créé par root : si Claude Code ne peut pas écrire dans `~/.claude`, en
  rendre la propriété à l'utilisateur du conteneur (`sudo chown -R node:node /home/node/.claude`
  dans le `postCreateCommand`).
- Un pare-feu lancé après `npm ci` laisse l'installation des dépendances sans restriction :
  l'activer avant. Un script de pare-feu doit aussi pouvoir être rejoué à chaque démarrage du
  conteneur.
- Dans un Codespace, `~/.claude` survit à un arrêt/redémarrage mais pas à un rebuild : le volume
  reste nécessaire. Pour ne pas se reconnecter d'un Codespace à l'autre, un secret Codespaces
  `CLAUDE_CODE_OAUTH_TOKEN` (généré par `claude setup-token`) fait l'affaire.

## Livrable

Un dépôt Argos avec un devcontainer fonctionnel et versionné, une authentification persistante,
et un fonctionnement identique constaté en local et en Codespace. Ce dépôt reproductible sert de
point de départ au lab M6, qui construit la fonctionnalité finale selon un cycle TDD discipliné.
