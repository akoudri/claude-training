# Utiliser Claude Code dans VS Code avec le LLM local (Ollama)

Ce tutoriel branche Claude Code (CLI et extension VS Code) sur l'Ollama de la stack `docker-compose.yml` de ce dépôt, au lieu de l'API d'Anthropic. Il explique **pourquoi** chaque variable d'environnement est nécessaire, et surtout le piège de la fenêtre de contexte, qui fait échouer une configuration par ailleurs correcte.

- **Configuration de référence** : les durées citées ont été mesurées sur celle du [tutoriel 01](01-configuration-open-webui.md) (Ryzen 7 7840HS, iGPU Radeon 780M, Ollama sous Vulkan, ~15,8 Go adressables). Le tutoriel fonctionne sur toute machine capable de faire tourner la stack ; seules les durées changent (voir le [tutoriel 01, section 2](01-configuration-open-webui.md#2-premier-démarrage)).
- **Modèle retenu** : `ornith-code`, une variante à contexte de 64k du modèle `ornith:9b` (5,6 Go)
- **Versions testées** : Ollama 0.35.1, Claude Code (CLI) 2.1.291, puis 2.1.292 pour le rejeu complet du tutoriel (CLI sur l'hôte, configuration de Claude Code vierge). Le **CLI** a été testé, y compris dans le dev container. Le **panneau de l'extension VS Code** `anthropic.claude-code` a été testé dans le dev container du [tutoriel 05](05-claude-code-sandbox-devcontainer.md) : il s'installe et répond, sans écran de connexion. Sur l'hôte, ses réglages suivent la documentation de l'extension et son schéma (lu sur la version 2.1.289 de l'extension, le CLI étant en 2.1.291).
- **Suite** : pour isoler l'agent du reste de la machine, voir [Isoler l'agent de code : sandbox et dev container](05-claude-code-sandbox-devcontainer.md)

> **Périmètre** : ce tutoriel couvre l'usage local. Un petit modèle de 9B n'a ni la qualité ni la vitesse d'un modèle hébergé par Anthropic : c'est un agent de code **utilisable sur des tâches ciblées**, pas un remplaçant. Les limites sont détaillées à la section 6.

Sources officielles utilisées (les réglages cités y ont été vérifiés) :

| Sujet | URL |
|---|---|
| Ollama et Claude Code | https://docs.ollama.com/integrations/claude-code |
| Extension VS Code, section « Use third-party providers » | https://code.claude.com/docs/en/vs-code |
| Variables d'environnement | https://code.claude.com/docs/en/env-vars |
| Fichiers de réglages (clé `env`) | https://code.claude.com/docs/en/settings-reference |
| Passerelles LLM (`ANTHROPIC_BASE_URL`) | https://code.claude.com/docs/en/llm-gateway |

---

## 1. Prérequis

| Élément | Détail |
|---|---|
| Stack démarrée | Comme au [tutoriel 01](01-configuration-open-webui.md#2-premier-démarrage), section 2. Depuis `local-llm/` : `docker compose up -d`, puis `docker compose ps` : le service `ollama` doit être *healthy*. Le port est lié à `127.0.0.1:11434` : l'API n'est joignable que depuis la machine. |
| CLI Claude Code | Linux, macOS, WSL2 : `curl -fsSL https://claude.ai/install.sh \| bash`. Windows (PowerShell) : `irm https://claude.ai/install.ps1 \| iex`. Puis `claude --version`. |
| Espace disque | ~6 Go de plus pour le modèle `ornith:9b` (section 2.3). |
| VS Code | Version **1.94.0 ou plus récente** (prérequis donné par la page de l'extension). |
| Extension | `anthropic.claude-code` (Extensions → « Claude Code »). Elle embarque sa propre copie du CLI pour le panneau de chat : le CLI autonome n'est nécessaire que pour lancer `claude` dans le terminal intégré. |

Vérifier que l'API répond avant toute configuration de Claude Code :

```bash
curl -s http://localhost:11434/api/version
# {"version":"0.35.1"}
```

> **À savoir** : l'installation et la mise à jour de Claude Code lui-même téléchargent depuis les serveurs d'Anthropic et depuis npm, même si les requêtes de modèle restent locales (voir 3.4).

---

## 2. Choisir et préparer le modèle

### 2.1 Pourquoi un contexte de 64k

La documentation d'Ollama pour Claude Code demande un modèle qui gère les **outils** (*tool calling*) et une fenêtre de contexte d'au moins **64k tokens**. Un agent de code n'est pas un chat : le prompt système de Claude Code est volumineux, et chaque lecture de fichier ou sortie de commande s'ajoute à l'historique.

La stack, elle, fixe `OLLAMA_CONTEXT_LENGTH=32768` (32k, dans le `.env` ; voir `.env.example`. 16384 n'est que la valeur de repli de `docker-compose.yml` si le `.env` ne la définit pas), parce que n8n et Open WebUI en dépendent. On ne touche pas à cette valeur globale : on crée une **variante** du modèle avec son propre `num_ctx`, grâce à un Modelfile.

### 2.2 Comparaison mesurée

Tâche d'essai : corriger une fonction `slugify` pour que `node --test` passe (2 tests sur 3 échouent au départ), avec le prompt :

> Les tests de slug.test.js échouent. Corrige slugify dans slug.js pour que node --test passe, sans modifier les tests. Vérifie en lançant node --test.

| Modèle | Où | Résultat | Durée |
|---|---|---|---|
| `ornith-code` (`ornith:9b`, 64k) | CLI sur l'hôte | 3/3 tests, 12 tours | 6 min 51 s |
| `ornith-code` | Dev container, accès direct à Ollama | 3/3 tests | 78 s |
| `ornith-code` | Dev container, via la passerelle `ollama-gateway` | 3/3 tests | 114 s |
| `ornith-code` | CLI sur l'hôte, rejeu du tutoriel (CLI 2.1.292), trois essais | 3/3 en 8 min (13 tours) ; 3/3 en 6 min 20 s (8 tours) avec `claude -p` sans autorisation, l'agent n'ayant pas pu lancer `node --test` (voir 4.2) ; un essai **en boucle** : la même réécriture de `slug.js` répétée une trentaine de fois, compaction comprise, arrêté au bout de 25 min avec 0 test sur 3 | 6 à 25 min |
| `granite4.2-code` (`granite4.2:8b`, 64k) | Dev container et CLI | Code finalement correct, mais l'agent **ne s'arrête jamais** : timeout de 25 min, sur deux essais | 25 min (timeout) |

Toutes ces mesures utilisent `CLAUDE_CODE_MAX_CONTEXT_TOKENS=65536` (section 3.2) et ont été faites sur la configuration de référence.

Deux enseignements :

- **`ornith-code` est le modèle recommandé.** `ornith:9b` (https://ollama.com/library/ornith) est décrit comme « A self-improving family of open-source models for agentic coding », avec un contexte natif de 256K.
- **Les durées varient beaucoup d'un essai à l'autre** : de 78 s à 8 min pour la même tâche. Ne pas se fier à une seule mesure.
- **Un essai peut boucler** : le modèle répète la même modification avec la même explication, sans progresser. Au bout de quelques minutes sans avancée, interrompre l'agent (Échap, ou Ctrl+C en mode `-p`), restaurer le fichier (`git checkout -- slug.js`) et relancer une session neuve.

`granite4.2:8b` reste le modèle de chat d'Open WebUI et de n8n. Dans une boucle d'agent de code, il aboutit à un code correct mais ne conclut pas : l'agent ne rend jamais la main.

### 2.3 Créer `ornith-code`

Depuis le dossier `local-llm/` :

```bash
docker compose exec ollama ollama pull ornith:9b
printf 'FROM ornith:9b\nPARAMETER num_ctx 65536\n' | docker compose exec -T ollama sh -c 'cat > /tmp/Modelfile && ollama create ornith-code -f /tmp/Modelfile'
docker compose exec ollama ollama list   # ornith-code doit apparaître
```

| Élément | Rôle |
|---|---|
| `FROM ornith:9b` | Part des poids déjà téléchargés : la variante ne duplique pas les 5,6 Go. |
| `PARAMETER num_ctx 65536` | Fixe le contexte à 64k pour ce modèle uniquement. `OLLAMA_CONTEXT_LENGTH` (32k) reste valable pour les autres modèles. |
| `exec -T` | Pas de terminal alloué : nécessaire quand l'entrée vient d'un tube. |

Pour obtenir `granite4.2-code` à titre de comparaison, remplacer `ornith:9b` par `granite4.2:8b` et `ornith-code` par `granite4.2-code`.

---

## 3. Configurer Claude Code

### 3.1 Où mettre la configuration

> **Attention** : ne mettez **pas** le bloc `env` ci-dessous dans `~/.claude/settings.json`. Ce fichier s'applique à **toutes** vos sessions Claude Code : elles basculeraient toutes sur le modèle local, y compris celles où vous travaillez avec les modèles d'Anthropic.

Deux emplacements limitent l'effet à un projet.

| Emplacement | Portée | Quand l'utiliser |
|---|---|---|
| `.claude/settings.local.json` du projet | Vous, dans ce projet uniquement (CLI et extension) | Recommandé. |
| Réglages utilisateur VS Code (`claudeCode.environmentVariables` + `claudeCode.disableLoginPrompt`) | L'extension, dans **toutes** les fenêtres VS Code de la machine | Si vous n'utilisez que l'extension et toujours avec le modèle local. Le CLI du terminal n'en profite pas. |

> **Panneau VS Code et écran de connexion** : même avec `.claude/settings.local.json`, le panneau de l'extension affiche encore l'écran de connexion Anthropic tant que `claudeCode.disableLoginPrompt` n'est pas coché dans les réglages VS Code (3.5). C'est un réglage de l'extension, qu'un fichier de réglages de Claude Code ne remplace pas. Le CLI du terminal n'en a pas besoin.

Sur `.claude/settings.local.json`, la documentation précise qu'il est « gitignored when Claude Code saves a setting to it ; add it to your gitignore if you create it by hand ». Créé à la main, il n'est donc **pas** ignoré automatiquement : ajouter `.claude/settings.local.json` au `.gitignore` du projet. Le fichier ne contient pas de secret ici (`ollama` n'est pas un vrai jeton), mais il n'a pas à être partagé avec l'équipe.

### 3.2 Le bloc `env` complet

`.claude/settings.local.json` :

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "http://localhost:11434",
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_MODEL": "ornith-code",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "ornith-code",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "ornith-code",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "ornith-code",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "65536",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
```

| Variable | Valeur | Ce que ça implique |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `http://localhost:11434` | Adresse de l'API d'Ollama, **sans** `/v1` (consigne de la documentation d'Ollama). Ollama expose une API compatible avec celle d'Anthropic. Selon la documentation des variables, un hôte autre qu'Anthropic désactive aussi par défaut la recherche d'outils MCP (*MCP tool search*). |
| `ANTHROPIC_AUTH_TOKEN` | `ollama` | Valeur envoyée dans l'en-tête `Authorization` (préfixée par `Bearer `). Ollama ne vérifie rien : la valeur est arbitraire, mais la variable doit exister. Sans identifiant de ce type, un login claude.ai enregistré reste l'identifiant actif (page « Other LLM gateways »). |
| `ANTHROPIC_API_KEY` | `""` | Neutralise une clé réelle exportée par le shell (voir 3.3). |
| `ANTHROPIC_MODEL` | `ornith-code` | Modèle de la session. `--model` et `/model` ont priorité sur cette variable. |
| `ANTHROPIC_DEFAULT_OPUS_MODEL`, `_SONNET_MODEL`, `_HAIKU_MODEL` | `ornith-code` | Modèle derrière chaque alias. Le modèle « haiku » sert aussi aux fonctions d'arrière-plan : sans ces trois variables, Claude Code demanderait à Ollama des noms de modèles d'Anthropic qu'il n'a pas. |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | `65536` | Fenêtre de contexte **réelle** du modèle. Indispensable, voir l'encadré ci-dessous. |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | Coupe le trafic non essentiel : mises à jour automatiques, télémétrie, rapports d'erreur, `/feedback`, notes de version, vérifications du badge de PR et vérifications de disponibilité (par exemple du mode rapide). Désactive aussi la récupération des *feature flags*, ce qui rend Remote Control indisponible. |

> **Piège rencontré** : Claude Code ne connaît pas le modèle `ornith-code`. Il affiche : « "ornith-code" isn't described by this version's model catalog … auto-compact keeps this session within 200k tokens (the context window it assumes) … set CLAUDE_CODE_MAX_CONTEXT_TOKENS to its real window ». Sans `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, Claude Code croit disposer de 200k tokens : il ne **compacte** jamais l'historique à temps, et **Ollama tronque le prompt en silence** (le contexte du modèle est de 64k). Le modèle ne reçoit alors plus le prompt complet. Mesure : première exécution en dev container sans la variable, **timeout de 25 min et 0 test sur 3** ; même exécution avec `CLAUDE_CODE_MAX_CONTEXT_TOKENS=65536` : **3/3 en 78 s**. Cette variable doit toujours être égale au `num_ctx` de la variante.

Selon la page des réglages, les valeurs de `env` des réglages de projet et locaux sont appliquées après la confirmation de confiance de l'espace de travail (*trust*), ou au démarrage en mode `-p`. Les variables de sélection de modèle et les limites sont classées comme sûres et prises en compte dès le démarrage.

### 3.3 Pourquoi `ANTHROPIC_API_KEY` est vide

Si votre shell exporte une vraie clé `ANTHROPIC_API_KEY`, deux règles de la documentation s'appliquent :

- `ANTHROPIC_API_KEY`, lorsqu'elle est définie, est utilisée **à la place** de l'abonnement, même connecté ; en mode non interactif (`-p`), la clé est toujours utilisée si elle est présente.
- Une valeur de `env` **écrase** la même variable exportée dans le shell, et pour annuler un export du shell, on la met à `""` : Claude Code traite une valeur vide comme non définie pour le choix du fournisseur.

Sans `"ANTHROPIC_API_KEY": ""`, une clé réelle du shell risquerait d'être présentée comme identifiant, alors que la session vise Ollama. Avec la chaîne vide, seul `ANTHROPIC_AUTH_TOKEN` reste.

> L'ordre complet de précédence des identifiants relève de la page « Authentication », qui ne fait pas partie des références consultées ici : seules les deux règles ci-dessus sont vérifiées.

### 3.4 Ce qui reste local, et ce qui ne l'est pas

| Flux | Avec cette configuration |
|---|---|
| Prompts, code lu, sorties d'outils | Envoyés **uniquement** au modèle local (`ANTHROPIC_BASE_URL` pointe sur Ollama). Le classifieur du mode *auto* utilise le **même** point d'accès (mesuré, voir 4.4 et le [piège du mode auto](05-claude-code-sandbox-devcontainer.md#mesures-sur-la-configuration-de-référence)) : il ne sort pas non plus. |
| Télémétrie, rapports d'erreur, mises à jour automatiques | Coupés par `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`. |
| Installation et mise à jour de Claude Code | Téléchargées depuis Anthropic et npm : à faire explicitement (`claude update`). |
| Contrôle de sécurité de WebFetch | Avant le premier accès à chaque nom d'hôte, il envoie ce nom à `api.anthropic.com`. Le réglage `skipWebFetchPreflight: true` le supprime (n'importe quel fichier de réglages) ; sans contrôle, WebFetch tente n'importe quelle URL : l'accompagner de règles de permission `WebFetch`. |
| Marketplace officiel de plugins | Son enregistrement automatique, au premier lancement interactif, n'est **pas** couvert par `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` ; le couper avec `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1`, avant ce premier lancement (le désactiver plus tard n'annule rien). |
| Modèles `:cloud` d'Ollama | Une requête vers un modèle `:cloud` (par erreur de nom, ou demandée par l'agent) ferait sortir le prompt vers ollama.com. La stack fixe `OLLAMA_NO_CLOUD=1` sur le service `ollama` : ces modèles sont refusés localement (mesuré, voir [le tutoriel 05](05-claude-code-sandbox-devcontainer.md#6-vérifications-mesurées)). |
| Recherche web ou outils MCP distants | Dépendent des outils que vous activez, indépendamment du modèle. Non couverts par ce tutoriel. |

### 3.5 Variante : réglages VS Code uniquement

Dans les **réglages utilisateur** de VS Code (*Preferences: Open User Settings (JSON)*), suivre la section « Use third-party providers » de la documentation de l'extension :

```json
{
  "claudeCode.disableLoginPrompt": true,
  "claudeCode.environmentVariables": [
    { "name": "ANTHROPIC_BASE_URL", "value": "http://localhost:11434" },
    { "name": "ANTHROPIC_AUTH_TOKEN", "value": "ollama" },
    { "name": "ANTHROPIC_API_KEY", "value": "" },
    { "name": "ANTHROPIC_MODEL", "value": "ornith-code" },
    { "name": "ANTHROPIC_DEFAULT_OPUS_MODEL", "value": "ornith-code" },
    { "name": "ANTHROPIC_DEFAULT_SONNET_MODEL", "value": "ornith-code" },
    { "name": "ANTHROPIC_DEFAULT_HAIKU_MODEL", "value": "ornith-code" },
    { "name": "CLAUDE_CODE_MAX_CONTEXT_TOKENS", "value": "65536" },
    { "name": "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "value": "1" }
  ]
}
```

| Réglage | Défaut | Rôle |
|---|---|---|
| `claudeCode.disableLoginPrompt` | `false` | Supprime l'écran de connexion Anthropic, prévu pour les configurations de fournisseur tiers. |
| `claudeCode.environmentVariables` | `[]` | Variables d'environnement du processus Claude lancé par l'extension. La documentation recommande de préférer les réglages de Claude Code pour une configuration partagée. |

> **Piège** : le schéma de l'extension (son `package.json`, lu sur la version 2.1.289 de l'extension, alors que le CLI testé est en 2.1.291) déclare `claudeCode.environmentVariables` avec la portée `machine`, et chaque entrée sous la forme `{ "name": …, "value": … }`. Un réglage de portée `machine` n'est **pas** pris en compte dans `.vscode/settings.json` d'un espace de travail : il faut le mettre dans les réglages utilisateur. Il s'applique alors à toutes les fenêtres, d'où la recommandation de la section 3.1 : préférer `.claude/settings.local.json`, limité au projet et valable aussi pour le CLI.

Les guides de fournisseurs de la documentation placent la configuration dans `~/.claude/settings.json`, « afin que les réglages soient partagés entre l'extension et le CLI ». C'est précisément ce que ce tutoriel déconseille ici (3.1).

---

## 4. Premier usage

### 4.0 Préparer un projet d'essai

L'exercice de la section 2.2 est fourni avec le dépôt (`exemples/claude-code-devcontainer/slug.js` et `slug.test.js`). Travaillez sur une **copie**, hors du dépôt, pour que les modifications de l'agent et le fichier `.claude/settings.local.json` ne s'y retrouvent pas. Depuis `local-llm/` :

```bash
mkdir -p ~/essai-claude-local
cp exemples/claude-code-devcontainer/slug.js exemples/claude-code-devcontainer/slug.test.js ~/essai-claude-local/
cd ~/essai-claude-local && git init -q && git add . && git commit -qm "exercice initial"
node --test        # 2 tests sur 3 échouent : c'est le point de départ
```

Créez ensuite dans ce dossier le fichier `.claude/settings.local.json` de la section 3.2, et ajoutez `.claude/settings.local.json` à son `.gitignore`. Pour rejouer l'exercice : `git checkout -- slug.js`.

### 4.1 Dans VS Code

1. Ouvrir le dossier du projet (celui qui contient `.claude/settings.local.json`).
2. Vérifier que `claudeCode.disableLoginPrompt` est coché dans les réglages VS Code (3.5) : sinon le panneau affiche l'écran de connexion Anthropic. Ouvrir le panneau Claude Code, et accepter la confiance de l'espace de travail si elle est demandée.
3. Lancer `/status` pour contrôler l'adresse de l'API et le modèle, et `/model` pour confirmer que le modèle actif est `ornith-code`.
4. Envoyer une première demande **courte et ciblée**, par exemple celle de la section 2.2 sur le projet d'essai ci-dessous.

> `/status` et `/model` sont des commandes de session. Les références locales confirment que `/model` prend le pas sur `ANTHROPIC_MODEL` ; elles ne détaillent pas l'affichage exact de `/status`.

Si l'écran de connexion Anthropic apparaît quand même, voir le tableau de la section 6.2. La page de l'extension note aussi que VS Code n'hérite pas toujours de l'environnement du shell : lancer `code .` depuis un terminal garantit qu'il l'hérite.

### 4.2 En ligne de commande, sans fichier

Pour un essai ponctuel, sans rien écrire sur le disque :

```bash
ANTHROPIC_BASE_URL=http://localhost:11434 \
ANTHROPIC_AUTH_TOKEN=ollama \
ANTHROPIC_API_KEY="" \
ANTHROPIC_MODEL=ornith-code \
ANTHROPIC_DEFAULT_OPUS_MODEL=ornith-code \
ANTHROPIC_DEFAULT_SONNET_MODEL=ornith-code \
ANTHROPIC_DEFAULT_HAIKU_MODEL=ornith-code \
CLAUDE_CODE_MAX_CONTEXT_TOKENS=65536 \
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
claude
```

Les variables ne valent que pour ce processus. Le même prompt en non interactif :

```bash
claude -p "Les tests de slug.test.js échouent. Corrige slugify dans slug.js pour que node --test passe, sans modifier les tests. Vérifie en lançant node --test." \
  --allowedTools "Bash(node --test*)"
```

En mode `-p`, personne ne peut répondre aux demandes d'autorisation : une commande qui en exige une est refusée. Sans `--allowedTools`, l'agent du rejeu a bien corrigé `slug.js`, mais ses deux tentatives de lancer `node --test` ont été refusées, et il a conclu sans avoir vérifié son travail. La modification des fichiers du dossier, elle, n'a pas été bloquée.

### 4.3 Avec `ollama launch claude`

La documentation d'Ollama décrit aussi la commande `ollama launch claude`, qui lance Claude Code configuré pour Ollama. Elle évite d'écrire les variables à la main. Les références consultées ne disent pas si elle positionne `CLAUDE_CODE_MAX_CONTEXT_TOKENS` pour une variante personnalisée, et elle n'a pas été testée ici : après un lancement ainsi, chercher l'avertissement de la section 3.2, et ajouter la variable s'il apparaît.

### 4.4 Messages normaux

Deux messages sur la sortie d'erreur sont **sans conséquence** :

| Message | Signification |
|---|---|
| `[claude-code:unrecognized_model]` | Claude Code ne connaît pas `ornith-code` : même cause que l'avertissement de 3.2. Le message reste affiché : c'est `CLAUDE_CODE_MAX_CONTEXT_TOKENS` qui corrige le comportement, pas le message. |
| Facturation du classifieur du mode *auto* indisponible via `localhost:11434` | Inoffensif, mais il implique que le classifieur du mode *auto* envoie ses requêtes **au même point d'accès**, donc au même modèle local. Conséquences mesurées : le classifieur expire parfois (« ornith-code is temporarily unavailable (timed out), so auto mode cannot determine the safety of Bash »), et il a **accepté** qu'une commande sandboxée ouvre un domaine externe. Avec un modèle local, préférer le mode manuel ou `acceptEdits` ; voir le [piège du mode auto](05-claude-code-sandbox-devcontainer.md#mesures-sur-la-configuration-de-référence). |

---

## 5. Conseils d'usage pour un petit modèle local

La génération plafonne à ~14 tokens/s sur la configuration de référence (voir le [tutoriel 01](01-configuration-open-webui.md), section 1), soit ~70 ms par token inutile. Mesurez le débit de votre machine (tutoriel 01, section 2, étape 7) : les conseils valent tant qu'il reste de l'ordre de quelques dizaines de tokens/s. Conséquences pour un agent de code :

| Conseil | Raison |
|---|---|
| Donner des **tâches ciblées**, sur **peu de fichiers** | Chaque fichier lu consomme du contexte, qui est limité à 64k ; au-delà, Claude Code doit compacter l'historique (*auto-compact*). |
| Éviter les gros dépôts et les demandes vagues (« améliore le projet ») | Le modèle explore, lit beaucoup, et perd le fil. Nommer les fichiers et la commande de vérification. |
| S'attendre à une **première réponse longue** | Le prompt système de Claude Code est volumineux ; il est lu à ~250 tokens/s avant le premier token généré. Les tours suivants sont plus rapides, tant que le modèle reste chargé. |
| **Une seule requête à la fois** | La stack tourne avec `OLLAMA_NUM_PARALLEL=1`. Ne pas lancer deux agents en parallèle ; l'extension peut ouvrir plusieurs conversations, mais elles se disputent le même Ollama. |
| Ne pas utiliser Open WebUI ni lancer un workflow n8n **pendant** une session | Même Ollama, même file d'attente (voir le [tutoriel 03](03-agent-n8n.md), section 5.4). |
| La mémoire ne garde pas tous les modèles à la fois | Mesuré sur la configuration de référence : `ornith-code` (64k) occupe 6,4 Go, 100 % GPU ; `granite4.2:8b` de n8n (32k) 8,1 Go ; `bge-m3` 664 Mo. Les trois ensemble feraient environ 15,2 Go, à la limite des ~15,8 Go adressables par l'iGPU. Avec `OLLAMA_MAX_LOADED_MODELS=2`, charger granite et bge-m3 a **évincé** `ornith-code`. Quand n8n ou Open WebUI tournent, le modèle de code est donc déchargé puis rechargé, et la requête suivante de Claude Code est plus lente. |
| Vérifier avec `ollama ps` | Avec un profil GPU, `docker compose exec ollama ollama ps` doit afficher `100% GPU` pour `ornith-code`. Un partage CPU/GPU signifie que la variante 64k ne tient pas en mémoire GPU : voir 6.2. |
| Utiliser git | L'agent modifie les fichiers du projet. Un `git status` et un `git diff` avant d'accepter ses changements. |

Pour un agent qui exécute des commandes de façon autonome, l'isoler vaut mieux que lui faire confiance : voir [Isoler l'agent de code](05-claude-code-sandbox-devcontainer.md).

---

## 6. Limites et dépannage

### 6.1 Limites

- **Qualité** : un modèle de 9B échoue sur des refactorings larges ou des bases de code qu'il ne connaît pas. Il réussit sur des corrections ciblées avec un test qui valide.
- **Durée imprévisible** : pour la même tâche, de 78 s à 8 min selon l'essai, et un essai sur trois du rejeu a bouclé sans aboutir (2.2).
- **Fonctions liées à Anthropic** : sur un fournisseur tiers, l'extension ne propose pas les fonctions qui exigent un compte claude.ai (jauges d'usage du forfait, dictée vocale, onglet Web des sessions cloud).
- **Recherche d'outils MCP** : désactivée par défaut quand `ANTHROPIC_BASE_URL` pointe un hôte autre qu'Anthropic ; `ENABLE_TOOL_SEARCH=true` la réactive si le point d'accès transmet les blocs `tool_reference`. Non testé avec Ollama.
- **Remote Control** : indisponible (hôte non Anthropic, et flags coupés par `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`).

### 6.2 Dépannage

| Symptôme | Cause probable | Remède |
|---|---|---|
| L'écran de connexion Anthropic s'affiche (« Not logged in · Please run /login ») | `claudeCode.disableLoginPrompt` non coché, ou variables non transmises à l'extension | Cocher `claudeCode.disableLoginPrompt`. Vérifier que `ANTHROPIC_AUTH_TOKEN` est défini et que le projet est approuvé. Recharger la fenêtre (*Developer: Reload Window*). |
| L'agent boucle sans fin, ou oublie ses consignes en cours de route | Contexte tronqué en silence par Ollama : `CLAUDE_CODE_MAX_CONTEXT_TOKENS` absent | Définir `CLAUDE_CODE_MAX_CONTEXT_TOKENS=65536` (égal au `num_ctx` de la variante). Voir l'encadré de 3.2. |
| Même symptôme alors que la variable est définie | La session utilise un modèle sans variante 64k (par exemple `ornith:9b`, à 32k par défaut dans cette stack) | `/model` : vérifier que le modèle est `ornith-code`, et `ollama show ornith-code` pour lire `num_ctx`. |
| Erreur « model not found », ou un modèle d'Anthropic apparaît dans les logs Ollama | Une des variables `ANTHROPIC_DEFAULT_*_MODEL` manque, ou `--model` impose un autre nom | Définir les quatre variables de modèle. `docker compose logs -f ollama` montre le nom demandé. |
| Le modèle utilisé n'est pas celui attendu | `/model` ou `--model` a pris le pas sur `ANTHROPIC_MODEL` | `/model` pour choisir `ornith-code`. |
| Première réponse très longue (plusieurs dizaines de secondes) | Prompt système volumineux (lu à ~250 tokens/s sur la configuration de référence), et modèle à recharger | Normal. Patienter ; les tours suivants sont plus courts. |
| Chaque première demande après une pause recharge le modèle | Le modèle a été déchargé : `OLLAMA_KEEP_ALIVE` (30 min dans cette stack) est expiré, ou un autre modèle (Open WebUI, n8n) l'a remplacé en mémoire | Reprendre dans les 30 minutes, ou augmenter `OLLAMA_KEEP_ALIVE` dans `docker-compose.yml` (la stack doit être recréée). |
| `ollama ps` affiche un partage CPU/GPU pour `ornith-code` | La variante 64k ne tient pas dans la mémoire du GPU | Créer une variante à `num_ctx 32768` et régler `CLAUDE_CODE_MAX_CONTEXT_TOKENS` à la même valeur. Claude Code compactera plus souvent l'historique, mais le modèle restera entièrement sur le GPU. |
| `connection refused` sur `localhost:11434` | Stack arrêtée | `docker compose up -d`, puis `curl -s http://localhost:11434/api/version`. |
| Le CLI utilise encore l'API d'Anthropic | Le fichier `.claude/settings.local.json` n'est pas dans le dossier de lancement, ou le dossier n'est pas approuvé | Lancer `claude` à la racine du projet ; `/status` pour contrôler l'adresse. |
| Message `[claude-code:unrecognized_model]` | Modèle inconnu du catalogue | Sans gravité si `CLAUDE_CODE_MAX_CONTEXT_TOKENS` est défini (voir 4.4). |
| L'agent répète la même modification avec la même explication, sans que les tests progressent | Boucle d'un petit modèle, même avec un contexte bien réglé (observé une fois sur trois lors du rejeu) | Interrompre, `git checkout -- <fichier>`, relancer une session neuve, si possible avec une consigne plus précise. |
| En `claude -p`, « permission denied » sur une commande de vérification | Mode non interactif : aucune demande d'autorisation possible | `--allowedTools "Bash(node --test*)"` (4.2). |

---

## 7. Récapitulatif

| Étape | Commande ou réglage |
|---|---|
| Variante à 64k | `ollama create ornith-code` avec `PARAMETER num_ctx 65536` |
| Où configurer | `.claude/settings.local.json` du projet, **pas** `~/.claude/settings.json` |
| API | `ANTHROPIC_BASE_URL=http://localhost:11434`, `ANTHROPIC_AUTH_TOKEN=ollama`, `ANTHROPIC_API_KEY=""` |
| Modèle | `ANTHROPIC_MODEL` et les trois `ANTHROPIC_DEFAULT_*_MODEL` = `ornith-code` |
| **Piège** | `CLAUDE_CODE_MAX_CONTEXT_TOKENS=65536` |
| Confidentialité | `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` |
| Vérification | `/status`, `/model`, `ollama ps` |

**Résultat** sur la configuration de référence : sur la tâche d'essai, `ornith-code` passe 3 tests sur 3 en 6 à 8 min depuis le CLI (un essai sur trois du rejeu a bouclé), et en 78 à 114 s dans le dev container (accès direct, puis via la passerelle).

### Pour aller plus loin

- **Isoler l'agent** : sandbox de commandes et dev container sur réseau interne, dans [Isoler l'agent de code](05-claude-code-sandbox-devcontainer.md).
- **Régler Ollama et le GPU** : [tutoriel 01](01-configuration-open-webui.md), sections 1 et 2.
- **Cohabitation avec les workflows n8n** : [tutoriel 03](03-agent-n8n.md), section 5.4.
