# Isoler l'agent de code : sandbox Claude Code et dev container

Ce tutoriel complète [Utiliser Claude Code dans VS Code avec le LLM local](04-claude-code-vscode-local.md). Un agent de code exécute des commandes et modifie des fichiers sur la base de ce que raconte un modèle de 9B : il faut décider **ce qu'il peut toucher**. Deux mécanismes sont décrits, avec ce que chacun isole et ce qu'il laisse passer, puis testés avec le modèle `ornith-code` de la stack de ce dépôt.

- **Configuration de référence** : les durées citées ont été mesurées sur celle du [tutoriel 01](01-configuration-open-webui.md) (Ryzen 7 7840HS, iGPU Radeon 780M, Ollama sous Vulkan), sous Ubuntu. Le tutoriel fonctionne sur toute machine capable de faire tourner la stack ; seules les durées changent (voir le [tutoriel 01, section 2](01-configuration-open-webui.md#2-premier-démarrage)).
- **Versions testées** : Ollama 0.35.1, Claude Code (CLI) 2.1.291, nginx 1.29-alpine (passerelle), image `node:22`, Docker Compose. Le **CLI** et le **panneau de l'extension VS Code** `anthropic.claude-code` ont été testés dans le dev container : ouvert par « Reopen in Container », le panneau s'installe malgré l'absence d'Internet, s'ouvre sans écran de connexion et corrige l'exercice.
- **Modèle** : `ornith-code` (variante à 64k de `ornith:9b`), créé comme à la section 2.3 du [tutoriel 04](04-claude-code-vscode-local.md#23-créer-ornith-code)
- **Fichiers de l'exemple** : [`exemples/claude-code-devcontainer/`](../exemples/claude-code-devcontainer/)
- **Prérequis** : le [tutoriel 04](04-claude-code-vscode-local.md) fait jusqu'à la section 4.0 (modèle `ornith-code` créé, projet d'essai `~/essai-claude-local`). Pour la partie B : VS Code avec l'extension **Dev Containers** (`ms-vscode-remote.remote-containers`), ou Node.js sur l'hôte pour la variante en ligne de commande. Les commandes `docker compose` se lancent depuis le dossier `local-llm/`.

Sources officielles utilisées :

| Sujet | URL |
|---|---|
| Sandbox des commandes Bash | https://code.claude.com/docs/en/sandboxing |
| Clés `sandbox.*` | https://code.claude.com/docs/en/settings-reference |
| Dev container | https://code.claude.com/docs/en/devcontainer |
| Conteneur de référence d'Anthropic | https://github.com/anthropics/claude-code/tree/main/.devcontainer |
| Ollama et Claude Code | https://docs.ollama.com/integrations/claude-code |
| Variables d'environnement | https://code.claude.com/docs/en/env-vars |

---

## 1. Quelle isolation choisir ?

| | Aucune isolation | Sandbox (`/sandbox`) | Dev container |
|---|---|---|---|
| Ce qui est isolé | Rien : l'agent a vos droits d'utilisateur. | Les commandes **Bash** et **Monitor** lancées par Claude, et leurs processus enfants : écritures limitées au projet, réseau via un proxy. | **Tout** le processus Claude Code : commandes, outils de fichiers, MCP, hooks. Il ne voit que l'espace de travail monté et un réseau Docker **interne**, où seule une passerelle vers Ollama est joignable. |
| Ce qui n'est **pas** isolé | Tout. | Les outils Read, Edit et Write, les serveurs MCP locaux et les hooks, qui tournent hors du sandbox. | Ce qui est monté dans le conteneur (le dépôt, un volume de configuration) et les routes de la passerelle. |
| Réseau | Libre. | Aucune route directe ; le proxy filtre par nom d'hôte. | Réseau Docker `internal` : aucune route vers Internet, aucun DNS externe ; seule la passerelle vers Ollama répond. |
| Coût de mise en place | Aucun. | Rien sous macOS. Sous Linux et WSL2 : `bubblewrap` et `socat`, éventuellement un profil AppArmor. | Docker, la stack (passerelle comprise) démarrée avant l'ouverture, une image à construire. |
| À choisir quand | Dépôt de test jetable, sans secret. | Usage quotidien sur vos projets, avec validation des actions. | Agent **autonome** (`--dangerously-skip-permissions`), dépôt tiers, ou besoin d'un cloisonnement réseau strict. |

Les deux se combinent mal sans précaution : le sandbox s'appuie sur `bubblewrap`, qui ne démarre pas dans un conteneur non privilégié (voir 2.7). Dans le dev container de ce tutoriel, **le conteneur est la frontière** et le sandbox n'est pas activé.

> **À retenir** : le sandbox protège contre les commandes Bash hasardeuses, pas contre un agent qui écrit un fichier avec l'outil Write. Le dev container ajoute la frontière du conteneur, et le réseau interne empêche l'envoi de données vers l'extérieur. Aucun des deux n'empêche l'agent de lire ce qui est accessible **à l'intérieur** de sa frontière : ne montez que ce qu'il doit voir.

---

# Partie A. Le mode sandbox de Claude Code

## 2. Le sandbox

### 2.1 Ce qu'il isole, ce qu'il n'isole pas

Le sandbox est une frontière appliquée par le système d'exploitation autour des commandes shell que Claude lance. Il est **désactivé par défaut**.

| Accès | Par défaut, dans le sandbox | Réglage pour le modifier |
|---|---|---|
| Écritures | Dossier de travail, dossier temporaire de l'utilisateur, dossiers ajoutés (`--add-dir`). Les chemins protégés restent en écriture interdite. | `sandbox.filesystem.allowWrite`, `sandbox.filesystem.denyWrite` |
| Lectures | **Presque toute la machine**, y compris `~/.ssh` et `~/.aws/credentials`. | `sandbox.filesystem.denyRead`, `sandbox.filesystem.allowRead` |
| Réseau | Aucune route directe : les connexions passent par un proxy local qui vérifie chaque hôte. La liste d'hôtes autorisés est vide au départ. | `sandbox.network.allowedDomains`, `sandbox.network.deniedDomains` |
| Variables d'environnement | Héritées de Claude Code, secrets compris. | `sandbox.credentials`, `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` |

Ce qui **échappe** au sandbox :

| Élément | Conséquence |
|---|---|
| Outils Read, Edit, Write, WebFetch, WebSearch | Ils suivent les **règles de permission**, pas le sandbox. Un `denyRead` n'empêche pas l'outil Read ; `allowedDomains` ne limite pas WebFetch. |
| Hooks, serveurs MCP locaux, serveurs LSP, commande de ligne d'état | Ils tournent avec **vos droits complets**. |
| Commandes tapées à la main après `!` | Hors sandbox dans la plupart des sessions. |
| Commandes de `excludedCommands` | Hors sandbox, par construction. |
| Nouvelle tentative hors sandbox (`dangerouslyDisableSandbox`) | Voir 2.5. |

Autres limites de la documentation : le proxy décide d'après le **nom d'hôte** demandé et n'inspecte pas le TLS par défaut ; les outils qui ignorent les variables de proxy (`ssh` simple, la plupart des pilotes de base de données) ne peuvent pas se connecter, même à un hôte autorisé ; seul le TCP passe (pas d'UDP, de QUIC ni d'ICMP). La documentation précise que le sandbox « réduit le risque » sans être une frontière d'isolation complète.

### 2.2 Prérequis selon le système

| Système | Prérequis |
|---|---|
| macOS | Aucun : le sandbox s'appuie sur Seatbelt, intégré au système. Passer directement à 2.4. |
| Linux, WSL2 | Les deux paquets ci-dessous. |
| Windows hors WSL2 | Sandbox non disponible : lancer Claude Code dans WSL2, ou utiliser le dev container de la partie B. |

Sous Linux et WSL2, le sandbox s'appuie sur deux paquets :

| Paquet | Rôle |
|---|---|
| `bubblewrap` | Outil de sandbox sans privilège, qui applique l'isolation du système de fichiers. |
| `socat` | Relais qui achemine le trafic réseau vers le proxy du sandbox. |

```bash
sudo apt-get install bubblewrap socat    # Ubuntu / Debian
sudo dnf install bubblewrap socat        # Fedora
sudo pacman -S bubblewrap socat          # Arch
```

Le contrôle de dépendances se fait au démarrage : relancer Claude Code après l'installation. Dans `/sandbox`, un onglet **Dependencies** liste ce qui manque ; s'il n'apparaît pas, tout est présent. Le filtre `seccomp` est optionnel (il ajoute le blocage des sockets Unix) : `npm install -g @anthropic-ai/sandbox-runtime`.

### 2.3 Ubuntu 24.04 et plus : le profil AppArmor

> **Piège rencontré** : sur Ubuntu 24.04 et plus récent, la politique AppArmor par défaut empêche `bwrap` de créer les espaces de noms utilisateur dont il a besoin. La machine de référence (Ubuntu) en avait besoin : sans le profil ci-dessous, le sandbox ne démarre pas. Les autres distributions sont rarement concernées, mais la vérification ci-dessous ne coûte rien.

Vérifier d'abord si la restriction est active :

```bash
sysctl kernel.apparmor_restrict_unprivileged_userns
```

- `0` : rien à faire.
- `No such file or directory` : la clé n'existe pas, rien à faire non plus.
- `1` : ajouter un profil qui accorde cette capacité à `bwrap` :

```bash
sudo tee /etc/apparmor.d/bwrap > /dev/null <<'EOF'
abi <abi/4.0>,
include <tunables/global>

profile bwrap /usr/bin/bwrap flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
EOF
```

Le profil ne s'applique qu'à `bwrap` lui-même, pas aux commandes qu'il exécute dans le sandbox. Puis recharger AppArmor :

```bash
sudo systemctl reload apparmor
```

### 2.4 Activer le sandbox : `/sandbox` et les deux modes

Dans une session, lancer `/sandbox`. Le panneau a trois onglets :

| Onglet | Rôle |
|---|---|
| **Mode** | Choisir l'approbation des commandes sandboxées. |
| **Overrides** | Autoriser ou non la nouvelle tentative hors sandbox (réglage `allowUnsandboxedCommands`). |
| **Config** | Afficher les réglages résolus, dont les chemins protégés. |

| Mode | Réglage équivalent | Comportement |
|---|---|---|
| **Auto-allow** | `sandbox.autoAllowBashIfSandboxed: true` (défaut) | Une commande qui s'exécute **dans** le sandbox est approuvée sans demande. Les règles `deny` et les règles `ask` ciblées (par exemple `Bash(git push *)`) restent appliquées. |
| **Regular permissions** | `sandbox.autoAllowBashIfSandboxed: false` | Toutes les commandes passent par le flux de permissions habituel, même sandboxées : plus de contrôle, plus de validations. |

Le choix est écrit dans `.claude/settings.local.json` du projet. Pour sandboxer tous les projets, mettre `sandbox.enabled` dans `~/.claude/settings.json`.

**Pour essayer** sur le projet d'essai du tutoriel 04 (`~/essai-claude-local`, qui contient déjà le `.claude/settings.local.json` pointant vers Ollama) : lancer `claude`, taper `/sandbox` et choisir *Auto-allow*. Demander ensuite à l'agent de lancer les commandes Bash `curl -sI https://example.com`, puis `echo test > ~/sandbox-test.txt`. Le `curl` est bloqué ou fait l'objet d'une demande d'autorisation (à refuser), et l'écriture hors du projet échoue en « système de fichiers en lecture seule », comme dans les mesures de 2.6. En mode `claude -p`, sans demande possible, le rejeu a obtenu pour le `curl` une réponse `HTTP/1.1 403 Forbidden` du proxy, avec l'en-tête `X-Proxy-Error: blocked-by-allowlist`. Passer par une commande Bash est important : l'outil Write, lui, n'est pas sandboxé (2.1).

Pour changer le sandbox le temps d'une session, sans écrire de fichier : `claude --settings '{"sandbox": {"enabled": true, "allowUnsandboxedCommands": false}}'`.

### 2.5 L'échappatoire `dangerouslyDisableSandbox` et le mode strict

Quand une commande échoue dans le sandbox, Claude peut la **relancer hors sandbox** avec le paramètre `dangerouslyDisableSandbox`. Qui approuve la relance dépend du mode de permissions :

| Mode de permissions | Relance hors sandbox |
|---|---|
| `bypassPermissions` | Sans aucune demande. |
| Manuel, `acceptEdits` | Demande « Bash command (unsandboxed) ». |
| `auto` | Un modèle classifieur examine la commande. |
| `dontAsk` | Refusée. |

Une règle `allow` qui correspond (`Bash(curl *)`, par exemple) approuve aussi la relance. Pour être prévenu quand même, ajouter une règle `ask` sur `Bash(dangerouslyDisableSandbox:true)`.

Le **mode strict** supprime l'échappatoire :

| Clé | Valeur | Effet |
|---|---|---|
| `sandbox.allowUnsandboxedCommands` | `false` | Claude Code **ignore** `dangerouslyDisableSandbox` : tant que le sandbox tourne, les commandes sont sandboxées, sauf celles de `excludedCommands`. L'onglet Overrides l'affiche comme *Strict sandbox mode*. |
| `sandbox.failIfUnavailable` | `true` | Claude Code **refuse de démarrer** si le sandbox ne peut pas démarrer. Sans cette clé, il exécute alors les commandes **sans sandbox**. |

Les deux vont ensemble : le mode strict sans `failIfUnavailable` laisse l'agent travailler sans protection dès qu'une dépendance disparaît.

### 2.6 Bloc recommandé pour le projet

À placer dans `.claude/settings.json` du projet :

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false,
    "filesystem": {
      "denyRead": ["~/"],
      "allowRead": ["."]
    }
  }
}
```

| Clé | Valeur | Ce que ça implique |
|---|---|---|
| `sandbox.enabled` | `true` | Active le sandbox. Défaut : `false`. |
| `sandbox.failIfUnavailable` | `true` | Pas de repli silencieux hors sandbox (2.5). |
| `sandbox.autoAllowBashIfSandboxed` | `true` | Les commandes sandboxées ne demandent pas de validation : c'est le mode auto-allow. Mettre `false` pour garder toutes les validations. |
| `sandbox.allowUnsandboxedCommands` | `false` | Supprime la relance hors sandbox. |
| `sandbox.filesystem.denyRead` | `["~/"]` | Interdit aux commandes sandboxées de lire le dossier personnel (clés SSH, identifiants cloud…). |
| `sandbox.filesystem.allowRead` | `["."]` | Rouvre la lecture du projet. Dans `.claude/settings.json`, `.` désigne la racine du projet ; dans `~/.claude/settings.json`, il désignerait `~/.claude`. |
| `sandbox.network.allowedDomains` | non défini | Liste vide : aucun hôte pré-autorisé. Un hôte hors liste dépend du mode de permissions (demande, refus, ou autorisation sans demande en `bypassPermissions`). |

Remarques à connaître :

- **`denyRead: ["~/"]` peut gêner les outils installés dans le dossier personnel** (gestionnaire de versions de Node, cache npm…). Ce bloc est celui de l'exemple de la documentation ; si une commande échoue en lecture, ajouter le chemin concerné à `allowRead` plutôt que de retirer la règle. Mesuré sur la configuration de référence : pour les commandes sandboxées, `~/.config` et `~/.bashrc` paraissent inexistants et le projet reste lisible, comme prévu ; mais le Node 22 installé par nvm (`~/.nvm`) devient invisible, et `node --version` répond `v20.14.0`, le Node du système, **sans aucune erreur**. Un binaire de `~/.local/bin` devient, lui, « commande introuvable » (ici, un hook qui réécrivait les commandes du shell vers un tel binaire les faisait toutes échouer). Pour nvm : `"allowRead": [".", "~/.nvm"]`.
- **Réglages de dépôt et réglages utilisateur** : la documentation indique qu'un `false` placé dans les réglages utilisateur, `--settings` ou les réglages gérés **l'emporte** sur un `true` du projet. Pour un sandbox qu'un dépôt ne peut pas assouplir, mettre `allowUnsandboxedCommands: false` dans `~/.claude/settings.json` ou passer par `--settings`.
- **`sandbox.network.strictAllowlist`**, qui refuse tout hôte hors liste au lieu de demander, ne s'accepte que dans les réglages utilisateur ou gérés, ou via `--settings` : un dépôt ne peut pas l'activer.
- **Le modèle n'a pas besoin d'être dans la liste réseau.** Les requêtes vers Ollama sont émises par le processus Claude Code, pas par une commande Bash. La documentation du sandbox dit que celui-ci couvre **les commandes shell**, que le proxy tourne hors du sandbox et que les outils intégrés suivent les permissions ; elle ne dit **pas** explicitement que les appels de l'API du modèle sont hors sandbox. La mesure ci-dessous le vérifie sur la configuration de référence.
- **Une commande sandboxée n'atteint pas l'Ollama de l'hôte.** Sous Linux, le `localhost` d'une commande sandboxée est privé : `curl http://localhost:11434` depuis Bash n'atteint pas le port de l'hôte. Pour tester l'API, le faire dans un terminal normal.

#### Mesures sur la configuration de référence

Test fait sur l'hôte avec `ornith-code`, le bloc ci-dessus (sans `filesystem`) passé par `--settings`, en mode de permissions **auto** (celui de la session). L'agent devait lancer un `curl` vers example.com, écrire dans `~/sandbox-test.txt`, puis corriger l'exercice `slug.js`.

| Essai | Résultat |
|---|---|
| Écriture dans `~/sandbox-test.txt` | **Refusée** : « Système de fichiers accessible en lecture seulement ». Le fichier n'existe pas après coup. |
| `curl https://example.com`, premier essai | **Bloqué** : `deny network-outbound example.com:443 (not in this command's allowed_domains …)`. |
| Même commande relancée par l'agent avec `allowed_domains: ["example.com"]` | **Autorisée : code HTTP 200.** |
| Correction de l'exercice | 3/3 tests, en 9 min 16 s. Le modèle local fonctionne bien avec le sandbox actif : aucun domaine n'a été ajouté pour Ollama. |
| Avec `sandbox.network.strictAllowlist: true`, même scénario | Premier essai bloqué (`host is not on the allow list`). Relance refusée : « allowed_domains cannot widen network access in this session ». |

> **Piège rencontré** : en mode **auto**, une commande sandboxée peut déclarer elle-même les hôtes dont elle a besoin (`allowed_domains`), et un **classifieur** décide. Avec un fournisseur tiers, ce classifieur passe par le même point d'accès, donc ici **le modèle local de 9B** : il a accepté example.com. Le sandbox seul ne garantit donc pas l'isolation réseau avec un modèle local en mode auto. La parade documentée est `sandbox.network.strictAllowlist: true`, mesurée efficace ci-dessus.

Comme un dépôt ne peut pas activer `strictAllowlist`, le placer dans les **réglages utilisateur** `~/.claude/settings.json` (il ne s'applique qu'aux sessions où le sandbox est actif) :

```json
{
  "sandbox": {
    "allowUnsandboxedCommands": false,
    "network": { "strictAllowlist": true }
  }
}
```

Autre possibilité : un fichier de réglages passé à chaque lancement, `claude --settings ~/claude-sandbox-strict.json`. Pour éviter la question en amont, ne pas utiliser le mode auto avec un modèle local : le mode manuel demande votre accord pour chaque hôte hors liste.

### 2.7 Sandbox et conteneur

Dans un conteneur non privilégié, `bubblewrap` ne peut pas monter un `/proc` neuf et les commandes sandboxées échouent avec `Can't mount proc on /newroot/proc: Operation not permitted`. La documentation propose `enableWeakerNestedSandbox: true`, qui « affaiblit considérablement » la sécurité et ne se justifie que si le conteneur offre déjà l'isolation voulue. Le dev container de la partie B n'embarque ni `bubblewrap` ni cette option, et n'a plus de pare-feu : le conteneur et son **réseau interne** (sans route ni DNS externes) **sont** la frontière.

---

# Partie B. Le dev container sur réseau interne

## 3. Principe

Le dev container fait tourner **tout Claude Code** dans un conteneur qui n'a **aucune route vers Internet**. Il est inspiré du conteneur de référence d'Anthropic, mais l'isolement vient du **réseau Docker**, pas d'un pare-feu dans le conteneur.

```text
 dev container  --(réseau llm-agents, internal)-->  ollama-gateway  -->  ollama:11434
   (user node)        pas de route Internet, pas de DNS externe   nginx, 3 routes     (réseau default)
```

| Élément | Rôle |
|---|---|
| Réseau `llm-agents` | Déclaré `internal: true` dans `docker-compose.yml`, avec un nom fixe (`name: llm-agents`). Pas de route vers Internet, pas de résolution DNS de noms externes. Le dev container ne rejoint **que** ce réseau. |
| Service `ollama-gateway` | nginx 1.29-alpine, sur les réseaux `default` et `agents`. Écoute sur 8080 et transmet vers `ollama:11434` **trois routes seulement**. |
| `ANTHROPIC_BASE_URL` | `http://ollama-gateway:8080` |

Les routes de la passerelle (`ollama-gateway/nginx.conf`) :

| Route | Méthode | Usage |
|---|---|---|
| `/v1/messages` | `POST` | L'API Messages compatible Anthropic : les requêtes du modèle. Délai de lecture de 1800 s et mise en tampon coupée, pour le *streaming* d'un modèle lent. |
| `/v1/messages/count_tokens` | `POST` | Comptage de tokens. |
| `/api/version` | `GET` | Test de joignabilité (utilisé au démarrage). |
| tout le reste | toutes | **403** : `pull`, `push`, `create`, `delete`, `tags`, etc. sont refusés. |

| | Conteneur de référence d'Anthropic | Cet exemple |
|---|---|---|
| Mécanisme | Pare-feu `iptables` dans le conteneur, avec `NET_ADMIN`, `NET_RAW` et `sudo` pour le script. | Réseau Docker `internal` ; aucune capacité ajoutée, pas de `sudo`. |
| Accès au modèle | `api.anthropic.com` autorisé. | **Ollama de la stack uniquement**, via la passerelle. |
| Sorties ouvertes | SSH sortant (port 22), `api.anthropic.com`, **tout le réseau /24 de l'hôte**, plages GitHub, npm, Sentry, Statsig, marketplace VS Code. | Aucune, hors les trois routes de la passerelle. |
| Réseau de l'hôte | Ouvert (/24). | Postgres, n8n, Open WebUI et Ollama (en direct) : noms introuvables. |
| Outils | zsh, git-delta, extensions de formatage. | Version allégée : `git`, `jq`, `nano`, `curl`. |

> **Pourquoi pas un pare-feu dans le conteneur** : une première version de cet exemple reprenait le pare-feu `iptables` de la référence. Une revue y a trouvé quatre défauts, qui tiennent à la **méthode** autant qu'au script :
>
> 1. **Fuite par le DNS.** Le résolveur intégré de Docker (`127.0.0.11`) transmet les requêtes de noms externes **depuis l'hôte** : les règles `iptables` du conteneur ne s'y appliquent pas. Un nom du type `<données>.domaine-attaquant.example` sort donc par le DNS.
> 2. **Échec ouvert.** Si le script échouait avant la pose des politiques `DROP`, le conteneur gardait tout l'accès à Internet.
> 3. **Toute l'API d'Ollama était joignable.** Un `pull` ou un `push` vers un registre contrôlé par un attaquant permettait de faire sortir des données, et un `delete` pouvait casser n8n ou Open WebUI, qui utilisent les mêmes modèles.
> 4. **`.devcontainer/` était modifiable par l'agent.** Il pouvait y ajouter un `initializeCommand`, exécuté **sur l'hôte** à la prochaine ouverture : une voie vers l'exécution de code sur la machine.
>
> La conception actuelle les traite à la racine : un réseau sans route ni DNS externes (1, 2), une passerelle qui n'expose que l'API Messages (3), et `.devcontainer/` monté en lecture seule (4). Leçon : un contrôle réseau placé **dans** le conteneur que l'agent contrôle est plus fragile qu'une frontière posée **à l'extérieur**.

Ollama reste lié à `127.0.0.1` sur l'hôte : le conteneur ne passe pas par le port de l'hôte, mais par la passerelle.

### Contrepartie : le conteneur est totalement hors ligne

`git push`, `npm install`, `pip install` et équivalents ne fonctionnent **pas** dans le conteneur : on les lance **sur l'hôte**. L'espace de travail est un montage direct du dossier de l'hôte, donc les fichiers sont les mêmes des deux côtés.

Dans le conteneur, `/workspace` n'est **pas un dépôt git** : le montage ne contient que le dossier `exemples/claude-code-devcontainer` du dépôt parent, sans son dossier `.git`. Les commandes git (`status`, `diff`, `checkout`, `commit`) se lancent donc **sur l'hôte**.

### Les faits de la documentation à connaître

- L'option `--dangerously-skip-permissions` est **refusée en root** : le conteneur tourne donc avec un utilisateur `node`.
- Même dans le conteneur, elle **n'empêche pas l'exfiltration de ce qui est accessible à l'intérieur** par une route ouverte : ici, seules celles de la passerelle le sont. Utiliser des dépôts de confiance, et **ne pas monter `~/.ssh`**.
- `CLAUDE_CONFIG_DIR` associé à un volume persiste la configuration.
- `DISABLE_AUTOUPDATER` : désactive les mises à jour automatiques en arrière-plan ; `claude update` à la main reste possible.

> Ces points viennent de la page https://code.claude.com/docs/en/devcontainer, qui ne fait pas partie des fichiers lus localement pour ce tutoriel : ils sont repris tels quels, et seuls `DISABLE_AUTOUPDATER` et `CLAUDE_CONFIG_DIR` sont recoupés avec la page des variables d'environnement.

## 4. Les fichiers de l'exemple

Dossier : `local-llm/exemples/claude-code-devcontainer/`, plus `local-llm/ollama-gateway/nginx.conf` et, dans `local-llm/docker-compose.yml`, le service `ollama-gateway` et le réseau `agents`.

| Fichier | Rôle |
|---|---|
| `.devcontainer/devcontainer.json` | Construction, réseau, volumes, variables, test de la passerelle au démarrage. |
| `.devcontainer/Dockerfile` | Image : `node:22`, outils de base, Claude Code 2.1.291 figé. |
| `local-llm/ollama-gateway/nginx.conf` | Les trois routes autorisées ; tout le reste en 403. |
| `slug.js`, `slug.test.js` | L'exercice : une fonction à corriger, trois tests. |

### 4.1 `devcontainer.json`

| Clé | Valeur | Ce que ça implique |
|---|---|---|
| `build.dockerfile`, `build.args` | `Dockerfile`, `TZ` (Europe/Paris par défaut), `CLAUDE_CODE_VERSION` = `2.1.291` | Construit l'image. La version est **figée** : le build est reproductible. |
| `runArgs: --network=llm-agents` | | Rejoint le réseau interne. **La stack doit tourner avant l'ouverture**, sinon ce réseau n'existe pas. Le nom est fixé dans `docker-compose.yml` (4.5). Aucune capacité (`--cap-add`) n'est demandée. |
| `customizations.vscode.extensions` | `anthropic.claude-code` | Demande l'installation de l'extension dans le conteneur. Testé : elle s'installe bien, bien que le conteneur n'ait pas Internet. |
| `customizations.vscode.settings` | `claudeCode.disableLoginPrompt: true` | Pas d'écran de connexion Anthropic dans le panneau de l'extension. |
| `remoteUser` | `node` | Utilisateur sans privilège ; `sudo` est absent de l'image. |
| `mounts` (volume) | `claude-code-local-config-${devcontainerId}` sur `/home/node/.claude` | Persiste la configuration et l'historique de Claude Code entre deux reconstructions. |
| `mounts` (`.devcontainer`) | dossier local `.devcontainer` sur `/workspace/.devcontainer`, **en lecture seule** | L'agent ne peut pas y ajouter un `initializeCommand` (exécuté sur l'hôte) ni assouplir l'isolement. |
| `workspaceMount`, `workspaceFolder` | dossier local monté en `bind` sur `/workspace` | L'agent travaille sur les **vrais fichiers de l'hôte** (voir 5.3). |
| `postStartCommand` | `curl -sf -m 5 http://ollama-gateway:8080/api/version && echo ' : passerelle Ollama joignable'` | Vérifie à chaque démarrage que la passerelle répond. |

Variables du conteneur (`containerEnv`) :

| Variable | Valeur | Rôle |
|---|---|---|
| `CLAUDE_CONFIG_DIR` | `/home/node/.claude` | Dossier de configuration, placé sur le volume. |
| `ANTHROPIC_BASE_URL` | `http://ollama-gateway:8080` | La passerelle, sans `/v1`. |
| `ANTHROPIC_AUTH_TOKEN` | `ollama` | Valeur factice : le conteneur ne détient **aucun** identifiant réel. |
| `ANTHROPIC_API_KEY` | `""` | Neutralise toute clé réelle (voir le [tutoriel 04](04-claude-code-vscode-local.md#33-pourquoi-anthropic_api_key-est-vide), 3.3). |
| `ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `${localEnv:CLAUDE_LOCAL_MODEL:ornith-code}` | Le modèle local pour tous les alias. Pour en essayer un autre, exporter `CLAUDE_LOCAL_MODEL` **sur l'hôte** avant d'ouvrir le conteneur. |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | `${localEnv:CLAUDE_LOCAL_CONTEXT:65536}` | Fenêtre réelle de la variante, surchargeable par `CLAUDE_LOCAL_CONTEXT` sur l'hôte. **Indispensable** (voir l'encadré ci-dessous). Si vous changez de modèle avec `CLAUDE_LOCAL_MODEL`, alignez cette valeur sur son `num_ctx`. |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | Pas de télémétrie, de rapports d'erreur ni de mise à jour. |
| `DISABLE_AUTOUPDATER` | `1` | Pas de mise à jour automatique. |

> **Piège rencontré** : Claude Code ne connaît pas `ornith-code` et suppose une fenêtre de 200k tokens. Sans `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, il ne compacte pas à temps et Ollama tronque le prompt en silence. Première exécution dans le dev container **sans** la variable : timeout de 25 min, 0 test sur 3. **Avec** : 3/3 en 78 s (accès direct) puis 114 s (via la passerelle). Détails dans le [tutoriel 04, 3.2](04-claude-code-vscode-local.md#32-le-bloc-env-complet). Le défaut est **65536** ; si `CLAUDE_LOCAL_MODEL` désigne un modèle d'un autre `num_ctx`, exporter aussi `CLAUDE_LOCAL_CONTEXT`.

### 4.2 `Dockerfile`

| Instruction | Ce que ça implique |
|---|---|
| `FROM node:22` | Image Node 22 complète. |
| `apt-get install … less git procps unzip jq nano curl` | Outils du quotidien. Plus d'`iptables`, d'`ipset` ni de `sudo`. |
| `npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}` | Installe Claude Code 2.1.291 en tant que `node`, dans un préfixe npm propre à l'utilisateur. |
| `USER node`, `ENV DEVCONTAINER=true`, `WORKDIR /workspace` | Utilisateur sans privilège, dossier de travail. |

La construction (`devcontainer up`) passe par le réseau de build par défaut de Docker : **npm n'atteint son registre qu'au build**. Une fois le conteneur lancé, plus rien ne sort.

### 4.3 `nginx.conf` de la passerelle

Chaque route est un bloc `location = …` exact avec `limit_except`, et `location /` renvoie `403`. Pour autoriser une route de plus (un nouveau point de l'API que Claude Code réclame), il faut **éditer ce fichier sur l'hôte** puis redémarrer la passerelle :

```bash
docker compose restart ollama-gateway
```

Le conteneur de dev ne peut pas le faire : le fichier est hors de son espace de travail.

### 4.4 `slug.js` et `slug.test.js`

L'exercice : `slugify` ne gère que les minuscules et les espaces. Les trois tests de `slug.test.js` demandent aussi de retirer les accents (`Été à Paris` donne `ete-a-paris`) et de réduire la ponctuation et les espaces multiples (`  Bonjour,   le monde ! ` donne `bonjour-le-monde`). Deux tests sur trois échouent au départ.

### 4.5 Nom du réseau

Par défaut, Docker Compose nomme un réseau `<dossier du projet>_<réseau>` : le nom changerait selon l'endroit où le dépôt est cloné. `docker-compose.yml` lui donne donc un nom fixe (`name: llm-agents`), repris tel quel dans `devcontainer.json`. Si une autre stack de la machine utilise déjà ce nom, changer les deux valeurs ensemble.

---

## 5. Utilisation

### 5.1 Ouvrir le conteneur

1. Démarrer la stack depuis le dossier `local-llm/`, **passerelle comprise** : `docker compose up -d`. Vérifier que `ollama-gateway` tourne (`docker compose ps`).
2. Vérifier que le modèle existe : `docker compose exec ollama ollama list` doit montrer `ornith-code`. Sinon, le créer comme au [tutoriel 04, 2.3](04-claude-code-vscode-local.md#23-créer-ornith-code).
3. Ouvrir **le dossier** `local-llm/exemples/claude-code-devcontainer` dans VS Code (*File → Open Folder*), et non la racine du dépôt : VS Code ne trouverait pas le `.devcontainer/`.
4. Palette de commandes : **Dev Containers: Reopen in Container**. La première construction télécharge l'image Node et installe Claude Code (c'est le seul moment où le réseau est utilisé).

Variante en ligne de commande, sans VS Code :

```bash
cd exemples/claude-code-devcontainer     # depuis local-llm/
npm exec --yes --package=@devcontainers/cli -- devcontainer up --workspace-folder .
```

Pour entrer ensuite dans le conteneur : `docker ps --filter label=devcontainer.local_folder --format '{{.Names}}'` donne son nom, puis `docker exec -it -u node <conteneur> bash`. La sous-commande `devcontainer exec` du même outil existe aussi, mais elle n'a pas été utilisée ici.

### 5.2 Lire le message de démarrage

La commande de démarrage doit afficher la version d'Ollama suivie de la confirmation :

```text
{"version":"0.35.1"} : passerelle Ollama joignable
```

Si elle échoue (aucun message, ou erreur de `curl`), la stack ne tourne pas ou la passerelle est arrêtée : voir le dépannage.

### 5.3 Lancer l'exercice

Dans le terminal du conteneur (dossier `/workspace`) :

```bash
claude
```

et saisir le prompt :

> Les tests de slug.test.js échouent. Corrige slugify dans slug.js pour que node --test passe, sans modifier les tests. Vérifie en lançant node --test.

Ou en non interactif, sans validations :

```bash
claude -p "Les tests de slug.test.js échouent. Corrige slugify dans slug.js pour que node --test passe, sans modifier les tests. Vérifie en lançant node --test." --dangerously-skip-permissions
```

Le fichier `slug.js` du dossier de l'hôte est **modifié directement**, puisque l'espace de travail est monté en `bind`. Pour rejouer l'exercice, restaurer le fichier **sur l'hôte** : `git checkout -- local-llm/exemples/claude-code-devcontainer/slug.js` depuis la racine du dépôt (`/workspace` n'est pas un dépôt git dans le conteneur).

**Quand `--dangerously-skip-permissions` est acceptable.** Avec cette conception, rien ne sort du conteneur sauf vers les trois routes de la passerelle, et le conteneur ne détient aucun identifiant réel (le jeton est le `ollama` factice) : il n'y a pas d'identifiants de Claude Code à protéger. Le risque qui reste est dans l'**espace de travail monté**. Conditions, ensemble :

| Condition | Pourquoi |
|---|---|
| Travail sous **git, sur l'hôte** | L'agent peut **modifier et supprimer n'importe quel fichier** du dossier monté, et ces changements sont ceux de l'hôte. `git status` et `git diff` sur l'hôte avant de conserver quoi que ce soit ; commiter avant de lancer l'agent. |
| **Rien de sensible dans le dossier monté** | Ni `~/.ssh`, ni identifiants cloud, ni `.env` : l'agent peut les lire. Ils ne peuvent plus sortir par le réseau, mais ils pourraient être copiés ou recopiés dans les fichiers du projet. |
| Dépôt de confiance, de préférence | Un dépôt piégé peut détourner l'agent ; ici il ne peut pas envoyer de données à l'extérieur, mais il peut **abîmer le contenu du dossier monté**. |
| Passerelle inchangée | Si vous ajoutez des routes à `nginx.conf` (4.3), vous élargissez ce que l'agent peut atteindre. |

`.devcontainer/` est monté en **lecture seule** : l'agent ne peut pas modifier la configuration du conteneur. Les fichiers hors de ce dossier restent modifiables.

### 5.4 Git, npm et le reste : sur l'hôte

Le conteneur est hors ligne. Pour installer des paquets, pousser du code ou lire l'historique :

1. Lancer `npm install`, `git commit` ou `git push` **sur l'hôte**, dans le dossier de travail partagé.
2. Le conteneur voit immédiatement les fichiers modifiés.

Ne pas chercher à ouvrir le réseau du conteneur : c'est ce qui fait la valeur de cette conception.

## 6. Vérifications mesurées

Mesures faites depuis l'intérieur du conteneur, dans l'état de l'exemple :

| Vérification | Résultat |
|---|---|
| `getent hosts example.com`, et un nom unique `probe-<horodatage>.example.org` | Non résolus |
| `curl http://1.1.1.1` | Code 000 : aucune route |
| Postgres, n8n, Ollama (en direct) | Noms introuvables sur le réseau `agents` |
| Passerelle `/api/version` | `{"version":"0.35.1"}` |
| Passerelle `/api/tags` et `POST /api/pull` | 403 |
| Passerelle `DELETE /api/delete` | 403 |
| Passerelle `GET /v1/messages` | 403 |
| Passerelle `POST /v1/messages` avec le modèle `glm-5.3:cloud` | Refusé localement : `ollama cloud is disabled: remote model is unavailable` |
| `touch /workspace/.devcontainer/x` | `Read-only file system` |
| Utilisateur | `node`, `sudo` absent, `claude 2.1.291` |
| Exercice `slugify` avec `--dangerously-skip-permissions` | 3/3 tests, **114 s** ; rejeu du tutoriel : 3/3 en **222 s** (12 tours) |

Le journal d'accès de la passerelle pendant l'exercice ne montre que `POST /v1/messages?beta=true` : 5 appels, tous en 200 (10 lors du rejeu). Toutes les autres vérifications de ce tableau ont été reproduites à l'identique lors du rejeu, sur une stack neuve.

> **Piège rencontré** : la passerelle filtre les **routes**, pas le **modèle** demandé. Avant l'ajout de `OLLAMA_NO_CLOUD=1` au service `ollama` (`docker-compose.yml`), une requête `/v1/messages` vers un modèle `:cloud` (par exemple `glm-5.3:cloud`) était transmise par Ollama à ollama.com : le prompt quittait la machine, même si la réponse était `Unauthorized` faute de compte. Avec `OLLAMA_NO_CLOUD=1`, Ollama refuse ces modèles sans aucun appel réseau (réponse en moins d'une milliseconde). Le réglage protège aussi n8n et Open WebUI. Documentation : https://docs.ollama.com/faq (« How do I disable Ollama Cloud features? »).

La passerelle résout le nom `ollama` à chaque requête (`resolver 127.0.0.11` dans `nginx.conf`) : si le conteneur Ollama est recréé et change d'adresse, elle suit sans redémarrage.

Une mesure antérieure, avec accès direct à Ollama (sans passerelle), donnait 78 s. Les durées varient beaucoup d'un essai à l'autre : de 78 à 222 s dans le conteneur, 6 à 8 min pour le CLI sur l'hôte, avec un essai qui a bouclé (voir le tutoriel 04), sur la configuration de référence. Le temps d'un seul essai n'est pas représentatif.

## 7. Dépannage

| Symptôme | Cause | Remède |
|---|---|---|
| Le `postStartCommand` échoue (pas de « passerelle Ollama joignable »), ou le conteneur ne démarre pas faute de réseau | Stack arrêtée, passerelle arrêtée, ou réseau `llm-agents` absent | `docker compose up -d` depuis `local-llm/`, puis `docker compose ps`. `docker network ls` doit lister `llm-agents`. |
| Erreur 403 de la passerelle dans un message de Claude Code | Claude Code appelle une route que `nginx.conf` ne transmet pas | Identifier la route (`docker compose logs ollama-gateway`), l'ajouter à `ollama-gateway/nginx.conf` **sur l'hôte**, puis `docker compose restart ollama-gateway`. N'ajouter que le nécessaire (5.3). |
| Passerelle joignable mais `connection refused` ou 502 | Ollama arrêté ou pas encore prêt | `docker compose ps` : `ollama` doit être *healthy*. |
| `git push` ou `npm install` échoue dans le conteneur | Normal : le conteneur est hors ligne | Les lancer sur l'hôte (5.4). |
| `git status` répond « not a git repository » dans le conteneur | `/workspace` ne contient pas le `.git` du dépôt parent | Lancer git sur l'hôte. |
| Boucle sans fin, 0 test réussi | `CLAUDE_CODE_MAX_CONTEXT_TOKENS` ne correspond pas au `num_ctx` du modèle | Voir l'encadré de 4.1. |
| Première réponse très lente | Le modèle de code a été évincé de la mémoire par n8n ou Open WebUI | Voir le tutoriel 04, section 5. Patienter ou laisser n8n et Open WebUI au repos. |
| `--dangerously-skip-permissions` refusée | Session en root | Utiliser l'utilisateur `node` (`whoami`). |
| `touch` ou écriture dans `.devcontainer/` : « Read-only file system » | Voulu : ce dossier est monté en lecture seule | Modifier la configuration **sur l'hôte**, puis reconstruire. |
| L'extension `anthropic.claude-code` ne s'installe pas dans le conteneur | Ne s'est pas produit lors du test, mais le conteneur n'atteint pas le marketplace : une installation qui en dépendrait échouerait | Lancer `claude` dans le terminal du conteneur (le CLI y est installé et testé). |

---

## 8. Récapitulatif

| Question | Réponse |
|---|---|
| Ce que protège le sandbox | Les commandes Bash et leurs enfants : écriture limitée au projet, réseau filtré. |
| Ce qu'il ne protège pas | Read/Edit/Write, MCP, hooks. |
| Prérequis | Rien sous macOS. Linux et WSL2 : `bubblewrap`, `socat`, et le profil AppArmor sous Ubuntu 24.04+. |
| Mode strict | `allowUnsandboxedCommands: false` **et** `failIfUnavailable: true`. |
| Ce que protège le dev container | Tout le processus Claude Code, sur un réseau Docker `internal` : ni route Internet, ni DNS externe. |
| Seule sortie | La passerelle `ollama-gateway` : `POST /v1/messages`, `POST /v1/messages/count_tokens`, `GET /api/version`. Le reste : 403. |
| Réseau du conteneur | `llm-agents`, `http://ollama-gateway:8080`, Ollama toujours lié à `127.0.0.1` sur l'hôte. |
| `.devcontainer/` | Monté en lecture seule : pas d'`initializeCommand` ajouté par l'agent. |
| Contrepartie | Hors ligne : `git push` et `npm install` se lancent sur l'hôte. |
| Ce qui reste exposé | L'espace de travail monté (modifications et suppressions directes) : utiliser git sur l'hôte. |
| Testé | CLI et panneau de l'extension VS Code dans le conteneur. |

### Pour aller plus loin

- **Configurer Claude Code pour le modèle local** : [tutoriel 04](04-claude-code-vscode-local.md).
- **Cohabitation avec Open WebUI et n8n** : [tutoriel 03](03-agent-n8n.md), section 5.4 ; une seule requête à la fois dans Ollama.
- **Comparer les approches d'isolation** : https://code.claude.com/docs/en/sandbox-environments (page citée par la documentation du sandbox, non consultée ici).
