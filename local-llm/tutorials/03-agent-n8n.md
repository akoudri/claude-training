# Construire un agent de conformité documentaire dans n8n

Ce tutoriel décrit le démonstrateur n8n de ce dépôt : il compare un **document analysé** (une proposition) à un **document référentiel** (un cahier des charges ou SOW), exigence par exigence, avec un LLM local. Il produit un rapport en local et envoie par mail une synthèse **pseudonymisée**. Il explique surtout **pourquoi** l'architecture est faite ainsi, et ce qui casse quand on s'en écarte.

- **Configuration de référence** : les durées citées ont été mesurées sur celle du [tutoriel 01](01-configuration-open-webui.md) (Ryzen 7 7840HS, iGPU Radeon 780M, Ollama sous Vulkan). Le tutoriel fonctionne sur toute machine capable de faire tourner la stack ; seules les durées changent (voir le [tutoriel 01, section 2](01-configuration-open-webui.md#2-premier-démarrage)).
- **Modèles** : `granite4.2:8b` (chat, contexte 32k) et `bge-m3` (embeddings, vecteurs de dimension 1024). Si `.env` désigne un autre modèle de chat, reporter son nom dans `MODEL` de `n8n/src/constants.mjs`, puis régénérer les workflows (`node n8n/scripts/build.mjs`).
- **Versions testées** : n8n 2.41.6, Postgres 16 + pgvector
- **Corpus des exemples** : uniquement le corpus fictif de `n8n/exemples/` (SOW « Projet Héron », proposition du prestataire « Novaltis », 10 exigences dont 2 omissions volontaires)

### Prérequis

| Élément | Détail |
|---|---|
| Stack | Démarrée et configurée comme au [tutoriel 01](01-configuration-open-webui.md#2-premier-démarrage), section 2. |
| Node.js 22 ou plus récent, sur l'hôte | Pour les tests, `build.mjs` et `deploy.sh` (`node --version`). Aucune dépendance npm à installer. |
| Bash | Pour `deploy.sh` : Linux, macOS, ou WSL2 sous Windows. |
| Un compte SMTP pour l'envoi des mails | Le tutoriel utilise Gmail (section 3.2). Tout autre serveur SMTP convient : seul le nom de l'identifiant dans n8n est imposé. |
| Dossier de travail | **Toutes les commandes se lancent depuis le dossier `local-llm/`.** |

---

## 1. Workflow ou agent ?

Deux patterns, qu'il faut savoir choisir.

| | Workflow | Agent |
|---|---|---|
| Qui décide des étapes ? | Le concepteur, une fois pour toutes. | Le LLM, à chaque exécution. |
| Appels au LLM | Prévisibles (nombre et ordre connus). | Variables : le modèle choisit ses outils et s'arrête quand il estime avoir fini. |
| Durée | Prévisible. | Difficile à borner. |
| Reproductibilité | Bonne. | Faible : deux exécutions peuvent suivre deux chemins. |
| À choisir quand | Le chemin est connu à l'avance. | Le chemin dépend du contenu (quelle recherche, combien de fois). |

### Pourquoi un agent libre échoue ici

Donner au modèle tout le référentiel et lui demander « analyse toutes les exigences avec tes outils » ne fonctionne pas avec un modèle de 8B sur une machine grand public (chiffres de la configuration de référence) :

| Contrainte | Conséquence |
|---|---|
| ~14 tokens/s en génération | Chaque token inutile coûte ~70 ms. Une boucle d'outils qui s'égare coûte des minutes. |
| Contexte de 32k, partagé entre prompt, résultats d'outils et réponse | Une liste de 10 à 25 exigences, avec les extraits trouvés pour chacune, sature le contexte avant la fin. |
| Modèle de 8B | Il perd le fil d'une longue liste : il oublie des exigences, ou rend un verdict global au lieu d'un verdict par exigence. |
| `OLLAMA_NUM_PARALLEL=1` | Pas de parallélisme possible pour compenser. |

### Le choix hybride

Le démonstrateur découpe donc la tâche : le **squelette est orchestré** (workflow), et seule la partie qui demande du jugement est confiée à un **agent borné**.

| Partie | Pattern | Détail |
|---|---|---|
| Validation des deux documents, lecture du référentiel | Workflow | Requête SQL, assemblage des extraits dans l'ordre du document. |
| Extraction de la liste des exigences | Workflow (un seul appel au LLM) | Le référentiel entier tient dans le contexte : c'est plus fiable qu'une recherche. Sortie structurée, 25 exigences au maximum. |
| Verdict sur **une** exigence | Agent | L'agent ne voit qu'une exigence à la fois. Il choisit ses recherches parmi deux outils, 4 itérations au maximum. |
| Rapport, synthèse, mail | Workflow (code, sans LLM) | Déterministe : la pseudonymisation ne passe jamais par un modèle. |

> **À retenir** : un agent reste utile quand la tâche est **courte et bornée**. On lui laisse la décision sur ce qui varie (quels termes chercher, faut-il élargir la recherche) et on garde en code tout ce qui peut l'être.

---

## 2. Architecture

### 2.1 Les workflows

| # | Workflow | Déclencheur | Rôle |
|---|---|---|---|
| 01 | Ingestion des documents | Manuel | Vide la table `n8n_vectors`, lit `/data/documents`, découpe, vectorise et indexe. Affiche un bilan d'extraits par document. |
| 02 | Analyse de conformité | Appelé par un autre workflow | Cœur de l'analyse : validation, extraction des exigences, boucle avec un agent par exigence, rapport local, appel du 03. |
| 02a | Formulaire d'analyse | Formulaire n8n | Collecte les deux noms de fichiers et lance le 02 **sans attendre sa fin**. |
| 03 | Synthèse et envoi | Appelé par le 02 | Pseudonymisation, contrôle bloquant, envoi du mail par SMTP. |
| 04 | Alerte d'échec | *Error Trigger* | Workflow d'erreur des workflows 01, 02, 02a et 03 : envoie un mail minimal. Il ne se déclenche que pour les exécutions « de production » (formulaire et sous-workflows qu'il appelle), voir section 8.3. |
| 90 | Test synthèse | Manuel | Teste le 03 seul, avec des données fictives (cas « contrôle OK » et « terme résiduel »). |
| 91 | Test analyse | Manuel | Lance le 02 sur le corpus fictif. |

Le 02 est séparé du formulaire (02a) pour pouvoir être testé en ligne de commande et par le 91 sans passer par un navigateur.

### 2.2 Schéma du flux

```text
documents/ ──► [01 Ingestion] ──► Postgres : table n8n_vectors (base rag)
                                         │
Navigateur ──► [02a Formulaire] ──► [02 Analyse] ◄──── lit les extraits
                                         │
                       ┌─────────────────┼───────────────────────┐
                       │                 │                       │
              Extraction des      Boucle : 1 agent        Assemblage du
              exigences (1 appel  par exigence            rapport Markdown
              LLM, sortie JSON)   (2 outils de recherche,       │
                                   4 itérations max.)           ▼
                                         │                reports/conformite-….md
                                         ▼
                                  [03 Synthèse et envoi] ──► mail pseudonymisé
                                         ▲
        (échec non prévu d'un workflow) ─┴─► [04 Alerte d'échec] ──► mail minimal
```

Les deux outils de l'agent :

| Outil | Portée | Usage prévu |
|---|---|---|
| `chercher_dans_document_analyse` | Filtré sur `metadata.source` = document analysé, 4 extraits | Première recherche, avec les termes clés de l'exigence. |
| `chercher_dans_corpus` | Tous les documents, 4 extraits | Seulement pour comprendre un terme du référentiel. |

Les verdicts possibles sont `couverte`, `partielle`, `non_couverte` et `indeterminee`. Le prompt système demande 3 recherches au plus, et n8n coupe l'agent à 4 itérations.

### 2.3 Ce qui est versionné, et ce qui ne l'est jamais

Les workflows ne sont pas écrits à la main : ils sont **générés** par des modules JavaScript (`n8n/src/workflows/*.mjs`) puis exportés en JSON dans `n8n/workflows/`. La logique sensible (pseudonymisation, verdicts, rapport) vit dans `n8n/lib/*.js`, testée par `node --test`, puis embarquée telle quelle dans les nœuds Code.

| Chemin | Monté dans n8n | Versionné | Contenu |
|---|---|---|---|
| `documents/` | `/data/documents` (lecture seule) | non (sauf `.gitkeep`) | Les documents à indexer. |
| `reports/` | `/data/reports` (lecture-écriture) | non (sauf `.gitkeep`) | Les rapports complets. |
| `n8n/config/` | `/data/config` (lecture seule) | non (sauf `*.example.json`) | Dictionnaire, destinataire du mail, table des identifiants locaux. |
| `n8n/workflows/` | importé | oui | JSON des workflows, sans identifiant d'instance. |
| `n8n/exemples/` | copié dans `documents/` pour les essais | oui | Corpus fictif et vérité terrain. |
| `n8n/src/`, `n8n/lib/`, `n8n/scripts/`, `n8n/test/` | non | oui | Générateurs, logique testée, scripts, tests. |

Les règles du `.gitignore` correspondantes : `documents/*`, `reports/*` et `n8n/config/*`, avec des exceptions pour `.gitkeep` et `n8n/config/*.example.json`. Aucune adresse personnelle, aucun mot de passe et aucun document réel n'est dans le dépôt.

---

## 3. Préparation

### 3.1 Démarrer la stack

```bash
cp .env.example .env     # puis éditer les secrets et le profil matériel (tutoriel 01, section 2)
docker compose up -d
docker compose exec ollama ollama ps   # après un premier appel : "100% GPU" avec un profil GPU
```

Ouvrir http://localhost:5678 et créer le compte propriétaire.

> **Premier accès** : n8n propose un assistant d'IA et un parcours de prise en main avec un « sandbox » (Daytona). Ce n'est pas nécessaire ici. **Ne choisissez jamais Daytona** : les données quitteraient la machine. Un identifiant « n8n Assistant model » peut apparaître : il est sans rapport avec le démonstrateur.

### 3.2 Les trois identifiants

Ils se créent dans l'interface de n8n (http://localhost:5678/home/credentials, bouton *Create credential*) et ne sont jamais versionnés.

> **Le nom compte.** n8n donne des noms par défaut (« Ollama account », « Postgres account »…), mais `deploy.sh` retrouve les identifiants **par leur nom exact**. Renommez-les comme ci-dessous, sinon le déploiement s'arrête avec « Identifiants à créer dans n8n avant le déploiement ».

| Nom exact | Type | Paramètres |
|---|---|---|
| `Ollama local` | Ollama | URL de base : `http://ollama:11434` |
| `Postgres rag` | Postgres | Hôte `postgres`, port `5432`, base `rag`, utilisateur et mot de passe de `POSTGRES_USER` / `POSTGRES_PASSWORD` dans `.env`, SSL désactivé |
| `Gmail SMTP` | SMTP | Hôte `smtp.gmail.com`, port `465`, SSL/TLS activé, utilisateur = l'adresse Gmail, mot de passe = **mot de passe d'application**. Avec un autre fournisseur, saisir ses propres hôte, port et identifiants, mais **garder le nom `Gmail SMTP`**. |

Pourquoi `postgres` et `ollama` comme noms d'hôte : n8n tourne dans le réseau Docker de la stack, il joint les autres conteneurs par le nom de leur service. `localhost` désignerait le conteneur n8n lui-même.

**Créer un mot de passe d'application Google**

Gmail refuse la connexion SMTP avec le mot de passe habituel du compte. n8n doit utiliser un **mot de passe d'application** : un code de 16 caractères, propre à cette application, et révocable à tout moment.

1. **Activer la validation en deux étapes.** Elle est obligatoire. Ouvrez <https://myaccount.google.com/security>, puis la rubrique « Comment vous connecter à Google ». Activez « Validation en deux étapes » et suivez l'assistant : téléphone, application d'authentification ou clé.
2. **Ouvrir la page des mots de passe d'application.** Allez sur <https://myaccount.google.com/apppasswords>. Google peut redemander le mot de passe du compte.
3. **Créer le mot de passe.** Dans « Nom de l'application », saisissez un nom parlant, par exemple `n8n conformite`, puis cliquez sur **Créer**.
4. **Copier le code affiché.** Il est présenté en 4 groupes de 4 lettres et n'est affiché **qu'une seule fois**. S'il est perdu, il faut en générer un nouveau.
5. **Le coller dans n8n.** Ouvrez http://localhost:5678/home/credentials et l'identifiant `Gmail SMTP`. Collez le code dans le champ *Password*, sans les espaces. Dans *User*, mettez l'adresse Gmail complète. Cliquez ensuite sur **Save** : n8n teste la connexion.
6. **Vérifier.** Une fois les workflows déployés (section 4), lancez le workflow « 90 – Test synthèse » (section 2.1) et contrôlez que le mail arrive.

| Situation | Cause et solution |
|---|---|
| La page `apppasswords` indique que l'option n'est pas disponible | Trois causes possibles : la validation en deux étapes n'est configurée qu'avec des clés de sécurité, la Protection Avancée est activée, ou le compte appartient à une organisation (Google Workspace professionnel ou scolaire). Dans ce dernier cas, l'administrateur doit autoriser l'option, sinon il faut utiliser un compte Gmail personnel. |
| `Invalid login` / `535-5.7.8 Username and Password not accepted` | Le mot de passe habituel a été saisi à la place du mot de passe d'application, ou le code contient une faute de frappe. Générez un nouveau code. |
| L'envoi échoue après un changement du mot de passe du compte | Google révoque tous les mots de passe d'application quand le mot de passe du compte change. Créez-en un nouveau et remplacez-le dans l'identifiant. |
| Fin de la démonstration | Supprimez le mot de passe d'application depuis la même page (icône corbeille) : n8n perd aussitôt l'accès au compte. |

> **Sécurité.** Le mot de passe d'application donne accès au compte Gmail entier, pas seulement à l'envoi. n8n le stocke chiffré avec sa clé `N8N_ENCRYPTION_KEY`. Utilisez de préférence un compte Gmail dédié à la démonstration.

### 3.3 `notification.json`

Copier le modèle puis le remplir :

```bash
cp n8n/config/notification.example.json n8n/config/notification.json
```

| Champ | Rôle |
|---|---|
| `destinataire` | Adresse qui reçoit la synthèse et les alertes : la vôtre, pour l'exercice. |
| `expediteur` | Adresse de l'identifiant `Gmail SMTP` (l'adresse Gmail, ou celle de votre compte SMTP). |

Le fichier est exclu de git. Si un champ manque, le workflow 03 s'arrête avec « notification.json incomplet ». Si le fichier est absent, les workflows 03 et 04 échouent tous les deux : aucun mail ne partira.

### 3.4 Le dictionnaire de termes sensibles

```bash
cp n8n/config/sensitive-terms.example.json n8n/config/sensitive-terms.json
```

Le modèle contient les termes du corpus fictif :

```json
{ "termes": [
  { "terme": "Acme Défense", "remplacement": "[CLIENT]" },
  { "terme": "Acme", "remplacement": "[CLIENT]" },
  { "terme": "Novaltis", "remplacement": "[PRESTATAIRE]" },
  { "terme": "Projet Héron", "remplacement": "[PROJET-1]" },
  { "terme": "Jeanne Martin", "remplacement": "[PERSONNE-1]" }
] }
```

| Élément | Comportement |
|---|---|
| Ordre de traitement | Les termes sont triés du plus long au plus court : « Acme Défense » est remplacé avant « Acme ». |
| Comparaison | Insensible à la casse, aux accents, aux espaces multiples, aux tirets et aux variantes d'apostrophe. Le remplacement respecte les limites de mots. |
| Adresses mail et URL | Les adresses mail et les URL commençant par `http(s)://` ou `www.` sont masquées par expression régulière, sans passer par le dictionnaire (`[EMAIL]`, `[URL]`). Les numéros de téléphone et les noms de domaine nus (par exemple `exemple.com`) ne le sont **pas** : les ajouter au dictionnaire si nécessaire. |
| Dictionnaire absent, vide ou mal formé | Le mail est réduit aux statistiques (section 8). Une seule entrée mal formée invalide tout le dictionnaire. |

> **Règle importante : un remplacement ne doit contenir aucun terme du dictionnaire.** Un remplacement comme `[CLIENT]` est sûr tant que « client » n'est pas lui-même un terme. Si on ajoute le terme « client » avec le remplacement `[CLIENT]`, le contrôle bloquant (section 8.2) retrouve « client » dans le texte déjà pseudonymisé, y voit un résidu sensible, et **le mail est réduit aux statistiques**. Ce comportement est voulu : il va dans le sens sûr, mais il prive du tableau. Choisir des remplacements neutres (`[X1]`, `[PROJET-1]`).

### 3.5 Accès aux fichiers dans n8n 2.x

n8n 2.x restreint par défaut la lecture et l'écriture de fichiers au dossier `~/.n8n-files`. Les nœuds *Read/Write Files from Disk* échouent donc sur `/data/documents`. Le `docker-compose.yml` de ce dépôt fixe :

```yaml
- N8N_RESTRICT_FILE_ACCESS_TO=/data/documents;/data/reports;/data/config
```

| Dossier | Usage |
|---|---|
| `/data/documents` | Lecture des documents à indexer. |
| `/data/reports` | Écriture des rapports. |
| `/data/config` | Lecture du dictionnaire et de la notification. |

Le séparateur est le point-virgule. Un dossier absent de la liste provoque une erreur d'accès refusé dès la lecture, même s'il est monté dans le conteneur.

Deux autres nœuds sont désactivés par défaut dans n8n 2.x : *Local File Trigger* et *Execute Command*. Le démonstrateur n'en utilise aucun, ce qui explique le déclenchement par formulaire et non par dépôt automatique d'un fichier.

---

## 4. Déploiement

### 4.1 Tester, construire, déployer

```bash
node --test "n8n/test/**/*.test.*"     # 55 tests, sans dépendance npm
node n8n/scripts/build.mjs             # régénère n8n/workflows/*.json (sans identifiant)
bash n8n/scripts/deploy.sh             # identifiants, build, import, publication, redémarrage
```

| Étape | Ce que ça fait |
|---|---|
| Tests | Vérifient la pseudonymisation, le rapport, les verdicts, l'évaluateur et la structure des workflows. |
| `build.mjs` | Génère les JSON à partir de `n8n/src/workflows/*.mjs`. Sans option, les JSON ne contiennent aucun identifiant d'instance : ce sont ceux qu'on versionne. |
| `deploy.sh` | 1. Lit les identifiants de l'instance (`SELECT name, id FROM credentials_entity`) et écrit `n8n/config/credentials.local.json`. 2. Génère les JSON avec ces identifiants dans un dossier temporaire. 3. Les importe (`n8n import:workflow --separate`). 4. Publie les workflows listés dans `PUBLISH_IDS`. 5. Redémarre n8n. |

### 4.2 Pourquoi `deploy.sh` publie des workflows

Avec n8n 2.x, un workflow **appelé par un autre** (sous-workflow) ou déclaré comme **workflow d'erreur** doit être **publié**. Sinon l'exécution échoue avec « Workflow is not active » (ou « not active and cannot be executed »). La publication se fait par CLI, puis un redémarrage :

```bash
docker compose exec -T n8n n8n publish:workflow --id=cnfAnalyse000002
docker compose restart n8n
```

`PUBLISH_IDS` vaut par défaut `cnfFormulaire02a cnfAnalyse000002 cnfAlerteEchec04 cnfSynthese00003` :

| Identifiant | Workflow | Pourquoi publié |
|---|---|---|
| `cnfFormulaire02a` | 02a, formulaire | Le formulaire n'est joignable que si le workflow est actif. |
| `cnfAnalyse000002` | 02, analyse | Sous-workflow du 02a et du 91. |
| `cnfSynthese00003` | 03, synthèse | Sous-workflow du 02. |
| `cnfAlerteEchec04` | 04, alerte | Workflow d'erreur des autres. |

Les workflows 01, 90 et 91 restent à déclenchement manuel et n'ont pas besoin d'être publiés.

### 4.3 Importer les JSON à la main

Sans `deploy.sh` (par exemple sur une autre instance), importer chaque fichier de `n8n/workflows/` depuis l'interface :

1. *Workflows → Create workflow → ⋯ → Import from file*, puis choisir le JSON (01, 02, 02a, 03, 04, 90, 91).
2. Ouvrir le workflow : les nœuds qui utilisent un identifiant affichent une alerte. **Resélectionner** l'identifiant dans chacun (`Ollama local`, `Postgres rag` ou `Gmail SMTP`).
3. Dans les réglages du workflow (*Settings → Error workflow*), choisir « 04 – Alerte d'échec » pour les workflows 01, 02, 02a et 03.
4. Publier le 02a, le 02, le 03 et le 04 (bouton *Publish*), puis redémarrer n8n.

Les identifiants de workflows sont fixés dans le code (`cnf…`). Un import manuel via l'interface leur en attribue de nouveaux : les nœuds *Execute Workflow* doivent alors pointer vers les nouveaux workflows. C'est l'une des raisons de préférer `deploy.sh`.

### 4.4 Réglages des nœuds à connaître

| Nœud | Réglage | Valeur | Raison |
|---|---|---|---|
| Ollama Chat Model | *Enable Thinking* | **false** | Il est actif par défaut. Comme avec Open WebUI (`think: Off`), `granite4.2:8b` produirait des milliers de tokens de réflexion invisibles. |
| Ollama Chat Model | `temperature` | 0.1 | Des verdicts reproductibles. |
| Ollama Chat Model | `numCtx` | **non fixé** | Le contexte de 32768 vient de `OLLAMA_CONTEXT_LENGTH`. Le changer ici force Ollama à recharger le modèle. |
| Recursive Character Text Splitter | taille / chevauchement | 1000 / 150 | Mêmes valeurs qu'Open WebUI, pour comparer à corpus égal. |
| AI Agent | itérations maximum | 4 | Garde-fou : borne le temps passé sur une exigence. |
| Form Trigger (v2.6) | `path` | dans `options`, avec un `webhookId` | Voir section 5.4. |

---

## 5. Utilisation

### 5.1 Ingestion

Copier les documents (DOCX de préférence, sinon Markdown ou PDF) dans `documents/`. Pour le corpus fictif :

```bash
cp n8n/exemples/sow-exemple.md "n8n/exemples/Proposition – Projet Héron, v2.md" documents/
docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n execute --id=cnfIngestion0001 2>&1 | grep -E -B1 '"extraits":|^  "status":|No file'
```

La commande affiche l'exécution complète en JSON, soit plusieurs milliers de lignes : le filtre `grep` n'en garde que le bilan (nom de chaque document suivi de son nombre d'extraits) et le statut final, `"status": "success"`.

On peut aussi ouvrir le workflow « 01 – Ingestion des documents » dans l'interface et cliquer sur *Execute workflow* : le bilan se lit dans le dernier nœud, `Bilan`.

> **Pourquoi `-e N8N_RUNNERS_BROKER_PORT=5690`** : l'instance qui tourne occupe déjà le port 5679, et `n8n execute` en lance une seconde dans le même conteneur : conflit de port. Donner un autre port à la CLI règle le problème.

Résultat mesuré sur le corpus fictif :

| Document | Extraits |
|---|---|
| `sow-exemple.md` | 3 |
| `Proposition – Projet Héron, v2.md` | 2 |
| **Total** | **5**, vecteurs de dimension 1024 (`bge-m3`) |

Le workflow vide d'abord la table (`DROP TABLE IF EXISTS n8n_vectors`) puis la reconstruit : l'opération est idempotente, sans doublon. Si `documents/` ne contient aucun fichier `.docx`, `.pdf` ou `.md`, l'ingestion échoue sur « No file(s) found » au lieu de laisser passer un index vide pour un succès.

Les extraits portent leur position dans le document (`metadata.loc.lines.from`) : c'est ce qui permet de reconstituer le référentiel dans l'ordre pour l'extraction.

### 5.2 Lancer une analyse

Ouvrir le formulaire : http://localhost:5678/form/analyse-conformite

| Champ | Valeur pour le corpus fictif |
|---|---|
| Document référentiel | `sow-exemple.md` |
| Document analysé | `Proposition – Projet Héron, v2.md` |

Les noms sont ceux de `documents/`, **exactement** (espaces, tiret long, accent et virgule compris) : le plus sûr est de les copier depuis la sortie de `ls documents/`. Le formulaire répond tout de suite : l'analyse continue en arrière-plan. À la fin, un rapport apparaît dans `reports/` (`conformite-AAAA-MM-JJ-HHMM.md`) et le mail de synthèse part.

Sans navigateur, le workflow « 91 – Test analyse » lance la même analyse sur le corpus fictif :

```bash
docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5690 n8n n8n execute --id=cnfTestAnaly0091 2>&1 | grep -v -i warn | tail -20
```

La commande attend la fin de l'analyse (plusieurs minutes), puis le rapport apparaît dans `reports/`. Les documents du corpus fictif doivent avoir été indexés (5.1).

### 5.3 Durées mesurées

Mesures de la configuration de référence ; elles varient comme la vitesse de génération de votre machine (tutoriel 01, section 2, étape 7).

| Mesure | Valeur |
|---|---|
| Analyse du corpus fictif (10 exigences) | **4 min 20 s à 4 min 50 s** (trois mesures) |
| Génération | ~14 tokens/s (`granite4.2:8b` sous Ollama/Vulkan, iGPU) |
| Ordre de grandeur par exigence | environ une demi-minute |
| Objectif sur un corpus réel | moins de 25 minutes |

Le temps dépend surtout de la longueur des justifications et du nombre de recherches de l'agent, donc de la taille du corpus. Le texte de confirmation du formulaire annonce 10 à 20 minutes, ce qui couvre un corpus plus volumineux que le corpus fictif.

### 5.4 Cohabitation avec Open WebUI

Ollama tourne avec `OLLAMA_NUM_PARALLEL=1` : **une seule requête à la fois**. Pendant une analyse, une question posée dans Open WebUI attend la fin de l'appel en cours (et inversement). Conséquences pratiques :

- ne pas utiliser Open WebUI pendant une analyse longue ;
- ne pas lancer deux analyses en même temps ;
- le modèle de chat et `bge-m3` restent chargés ensemble (`OLLAMA_MAX_LOADED_MODELS=2`), ce qui évite des rechargements entre l'agent et ses recherches.

### 5.5 Pièges n8n 2.x rencontrés

| Symptôme | Cause | Remède |
|---|---|---|
| L'URL du formulaire renvoie 404 | Le *Form Trigger* v2.6 attend le chemin dans `options.path` et un `webhookId` | Déjà corrigé dans le générateur (`02a-formulaire.mjs`). En import manuel, vérifier que le webhook est enregistré. |
| « Workflow is not active » à l'appel d'un sous-workflow | Sous-workflow non publié | `n8n publish:workflow --id=…` puis redémarrage (section 4.2). |
| Erreur d'accès refusé à la lecture ou à l'écriture d'un fichier | Dossier absent de `N8N_RESTRICT_FILE_ACCESS_TO` | Section 3.5. |
| Port 5679 déjà utilisé avec `n8n execute` | L'instance en cours occupe le port des runners | `-e N8N_RUNNERS_BROKER_PORT=5690`. |
| Génération interminable, réponse vide | *Enable Thinking* actif sur le modèle Ollama | Le désactiver (section 4.4). |
| Identifiants introuvables au déploiement | Noms par défaut (« Ollama account »…) | Renommer en `Ollama local`, `Postgres rag`, `Gmail SMTP`. |
| Mail d'échec « Extraction des exigences impossible : sortie du modèle invalide après 3 tentatives » dès le début de l'analyse | Ollama arrêté ou injoignable : le nœud reçoit une erreur au lieu d'une réponse, et l'échec est rapporté comme une sortie invalide (constaté en arrêtant le service `ollama`) | `docker compose ps` : `ollama` doit être *healthy*. Relancer l'analyse. |

---

## 6. Lire une exécution

L'historique de n8n (*Executions*) est l'outil de diagnostic. Il montre ce que le rapport ne montre pas : le **raisonnement** de l'agent.

### 6.1 Où regarder

Ouvrir l'exécution du workflow « 02 – Analyse de conformité », puis :

| Nœud | Ce qu'on y voit |
|---|---|
| `Extraits du référentiel` | Les extraits lus en base pour le référentiel. |
| `Reconstituer le référentiel` | Le texte complet remis au LLM, dans l'ordre du document. |
| `Extraire les exigences` et `Format des exigences` | La liste structurée (id, intitulé, description, type) renvoyée par le modèle. |
| `Analyser l'exigence` | Un passage par exigence. Dans le panneau de logs, on déplie chaque appel : la requête formulée par l'agent, l'outil choisi (`chercher_dans_document_analyse` ou `chercher_dans_corpus`) et les 4 extraits renvoyés. |
| `Format du verdict` | La sortie structurée brute : `statut`, `justification`, `citations`. |
| `Normaliser le verdict` | Le verdict **après contrôle** par le code. |
| `Verdict en erreur` | Les exigences dont l'agent a échoué deux fois ou n'a pas conclu. |

### 6.2 Verdicts rejetés

Le code contrôle ce que l'agent déclare :

| Constat dans `Normaliser le verdict` ou `Verdict en erreur` | Signification |
|---|---|
| Justification qui commence par « Verdict « couverte » rejeté : aucune citation du document analysé. » | L'agent a conclu `couverte` sans citer d'extrait de la proposition. Le statut est ramené à `indeterminee`. |
| « Statut invalide (« … »). » | Le modèle a rendu un statut hors de la liste. Il est ramené à `indeterminee`. |
| « Recherche non concluante. » | L'agent a épuisé ses 4 itérations sans conclure. |
| « Erreur d'analyse. » | L'agent a échoué après une nouvelle tentative. La boucle continue avec l'exigence suivante. |

La comparaison de la source citée est tolérante : elle ignore la casse, le chemin éventuel (`documents/Proposition – Projet Héron, v2.md`) et la normalisation Unicode. Les noms de fichiers avec espaces, accents, virgule et tiret long traversent ainsi la requête SQL, le filtre de métadonnées et la comparaison sans être tronqués.

> **Astuce de diagnostic** : si une exigence est `non_couverte` alors qu'elle est dans la proposition, ouvrir `Analyser l'exigence` et lire les extraits renvoyés. Si le passage attendu n'y figure pas, le problème est dans la recherche (requête de l'agent, découpage), pas dans le jugement.

### 6.3 Lire le rapport

Le rapport `reports/conformite-….md` contient :

| Partie | Contenu |
|---|---|
| En-tête | Noms des deux documents, date, durée. |
| Synthèse | Nombre d'exigences par statut. |
| Tableau de conformité | ID, type, intitulé, statut, justification. |
| Citations | Par exigence : `[source] « extrait »`. |

Le nom du fichier ne contient pas le nom des documents.

---

## 7. Résultats

### 7.1 Corpus fictif

Le script `n8n/scripts/evaluate-report.mjs` compare un rapport à la vérité terrain (`n8n/exemples/verite-terrain.json`) :

```bash
node n8n/scripts/evaluate-report.mjs reports/conformite-AAAA-MM-JJ-HHMM.md
```

Critères d'acceptation : toutes les exigences présentes, au moins 80 % de statuts justes, omissions détectées, et chaque `couverte` cite le document analysé.

| Exigence (corpus fictif) | Statut attendu | Pourquoi |
|---|---|---|
| EX-03 Prototype de transformation | partielle | La proposition exclut les aspects comportementaux. |
| EX-04 Formation | partielle | Une journée proposée, deux demandées. |
| EX-09 Support | non_couverte | **Omission volontaire.** |
| EX-10 Guide de modélisation | non_couverte | **Omission volontaire.** |
| Les six autres | couverte | Chaque exigence est traitée dans la proposition. |

Mesures sur le corpus fictif :

| Indicateur | Valeur |
|---|---|
| Score de `evaluate-report.mjs` | **10/10**, critères satisfaits |
| Omissions (EX-09, EX-10) | détectées |
| Durée de l'analyse | **4 min 20 s à 4 min 50 s** |
| Tests unitaires | 55 réussis |
| Risques R1 à R4 | tous levés, aucun repli appliqué (section 9.1) |

### 7.2 Corpus réel

L'analyse a aussi été lancée sur un corpus réel, et son rapport a été relu par l'utilisateur, qui l'a jugé conforme à ses attentes. Aucun contenu de ce corpus n'est reproduit ici.

### 7.3 Comparaison avec l'assistant « Expert MBSE » d'Open WebUI

La même demande a été posée à l'assistant « Expert MBSE » d'Open WebUI, sur le corpus réel : « Établis un tableau de conformité entre les livrables du SOW et la proposition ». **Toutes les exigences ont été traitées**, et le rapport de l'agent n8n a été jugé conforme aux attentes.

Les deux approches ne répondent pas au même besoin :

| Critère | Expert MBSE (Open WebUI) | Agent de conformité (n8n) |
|---|---|---|
| Déclenchement | Question libre dans le chat | Formulaire, référentiel et document à analyser désignés |
| Méthode | Un seul appel, avec les extraits RAG les plus proches (Top K 8) | Une analyse bornée par exigence, avec ses propres recherches |
| Sortie | Tableau dans la conversation | Rapport Markdown dans `reports/` et mail pseudonymisé |
| Contrôles | Aucun : la réponse est à relire | Statut sur liste fermée, « couverte » exige une citation, vérification des fuites avant l'envoi |
| Usage | Exploration, questions ponctuelles | Revue répétable et traçable |

---

## 8. Confidentialité

Les documents sont confidentiels : seule une synthèse pseudonymisée sort de la machine, par mail.

### 8.1 Contenu exact du mail

| Élément | Dans le mail |
|---|---|
| Statistiques par statut | oui |
| ID, intitulé pseudonymisé, statut | oui, si le contrôle bloquant est satisfait |
| Justifications, citations | **jamais** |
| Noms des documents, chemin du rapport | **jamais** (seulement la date et l'heure) |
| Message d'erreur brut | **jamais** |

Exemple tiré du workflow « 90 – Test synthèse » (contrôle satisfait). L'intitulé « Inventaire des modèles pour Acme Défense » devient :

```text
EX-01 | Couverte | Inventaire des modèles pour [CLIENT]
```

Sur le corpus fictif, les intitulés extraits par le modèle (« Inventaire des modèles », « Formation »…) ne contiennent en général aucun terme du dictionnaire : le tableau du mail est alors identique à celui du rapport.

L'objet du mail est de la forme `[n8n] Analyse de conformité – <date> – <couvertes>/<total> couvertes`.

### 8.2 Contrôle bloquant

Après le remplacement, le texte du tableau est examiné une seconde fois, plus strictement : on réduit texte et termes à leurs lettres et chiffres (sans espaces, tirets ni apostrophes) et on cherche chaque terme du dictionnaire. Cela attrape « AcmeCorp », « Acme-Défense » ou « Acme  Défense » que le remplacement par mots entiers a laissés.

| Situation | Mail envoyé |
|---|---|
| Aucune occurrence résiduelle | Statistiques + tableau pseudonymisé |
| Au moins une occurrence | Statistiques seules + « Synthèse détaillée retirée : N occurrence(s) sensible(s) résiduelle(s) ». Les termes ne sont pas cités. |
| Dictionnaire absent, vide ou invalide | Statistiques seules + la raison (« dictionnaire indisponible », « vide » ou « invalide ») |

Le workflow « 90 – Test synthèse » le montre avec « Intégration AcmeCorp » : « AcmeCorp » n'est pas remplacé (le mot entier est « AcmeCorp », pas « Acme »), mais le contrôle strict le détecte et le mail est réduit aux statistiques.

**Limites du contrôle** :

- il ne protège que les termes **du dictionnaire** : un nom non listé passe. C'est pourquoi justifications et citations, qui sont du texte libre, restent en local ;
- il peut produire de faux positifs (un terme court, un remplacement qui contient un terme, section 3.4), qui réduisent le mail au lieu de le laisser fuiter : la direction d'erreur est volontairement la plus sûre.

### 8.3 Alerte d'échec sans message d'erreur

Si un workflow s'arrête sur une erreur non prévue, le workflow 04 envoie uniquement :

- le nom du workflow ;
- l'étape en échec ;
- l'heure ;
- le numéro de l'exécution à consulter dans n8n.

**Jamais le message d'erreur** : il peut contenir des extraits de documents. Il reste dans l'historique des exécutions, sur la machine.

Quand l'alerte part-elle ? n8n n'appelle un workflow d'erreur que pour une exécution **qui n'est pas manuelle** :

| Lancement | Alerte 04 |
|---|---|
| Formulaire 02a, et les workflows 02 et 03 qu'il déclenche | ✅ |
| Bouton *Execute workflow* de l'éditeur (01, 90, 91) | ❌ : n8n ne déclenche jamais de workflow d'erreur pour une exécution manuelle |
| Ligne de commande `n8n execute` (sections 5.1 et 5.2) | ❌ en pratique : n8n tente l'appel, mais la commande se termine avant (« Cannot use a pool after calling end on the pool » dans la sortie) |

Dans les deux derniers cas, l'erreur se lit dans la sortie de la commande ou dans *Executions*. Une ingestion lancée sur un dossier `documents/` vide s'arrête ainsi sur « No file(s) found » sans mail d'alerte.

Les échecs prévus (document non indexé, aucune exigence extraite) passent, eux, par le workflow 03 en mode `echec`. Le motif y est une phrase construite par le code. Pour un document non indexé, elle ne contient que des comptes (« Document(s) demandé(s) non indexé(s) : N. Documents indexés : M. »), jamais de nom de document : les noms de fichiers portent des références que le dictionnaire ne couvre pas, et le détail se lit dans l'historique d'exécution n8n. La phrase reste pseudonymisée et soumise au même contrôle avant envoi. Le cas du référentiel trop long pour le contexte relève, lui, du workflow 04 (section 9.2).

---

## 9. Limites et pistes

### 9.1 Risques R1 à R4 et replis

Quatre hypothèses techniques ont été vérifiées avant de construire les workflows. Chacune avait un repli prévu.

| # | Question | Résultat | Repli appliqué |
|---|---|---|---|
| R1 | Le nœud Ollama Chat Model peut-il désactiver la réflexion de `granite4.2:8b` ? | Oui (*Enable Thinking* à false) | Aucun |
| R2 | `granite4.2:8b` appelle-t-il correctement les outils via l'AI Agent ? | Oui | Aucun |
| R3 | Les extraits portent-ils leur position pour reconstituer le référentiel ? | Oui (`metadata.loc.lines.from`) | Aucun |
| R4 | Le filtre de métadonnées PGVector accepte-t-il une expression issue du formulaire ? | Oui | Aucun |

Aucun repli n'a donc été appliqué.

### 9.2 Limites connues

| Limite | Détail et atténuation |
|---|---|
| **Injection de prompt** | Un document local piégé pourrait contenir des consignes qui orientent les verdicts de l'agent. Atténuations en code : un verdict `couverte` exige une citation du document analysé, la sortie passe par un parseur structuré, et le statut est limité à une liste fermée. Ce n'est pas une garantie : relire le rapport reste nécessaire, et il ne faut indexer que des documents de confiance. La vérification des citations porte sur le nom de la source citée, pas sur l'extrait reproduit mot pour mot. |
| **Référentiel trop long** | Au-delà de 80 000 caractères (~20 000 tokens), Ollama tronquerait le prompt sans le dire : l'analyse s'arrête donc avec un message clair. Mais ce cas ne déclenche que l'alerte brute du workflow 04 (nom, étape, heure), pas le mail motivé du workflow 03. |
| **Plus de 25 exigences** | Seules les 25 premières sont analysées. La troncature n'est plus silencieuse : le rapport commence par un avertissement (« N exigences extraites, seules les 25 premières ont été analysées ») et le mail contient la même ligne, qui ne comporte que des nombres. Pour les couvrir toutes, scinder le référentiel. |
| **Ingestion interrompue** | Le `DROP TABLE` du workflow 01 s'exécute **avant** la lecture des fichiers. Une ingestion qui échoue laisse l'index vide ou partiel : relancer le workflow. |
| **Signature du mail d'échec** | Elle indique « Rapport complet : dossier reports/ », alors qu'aucun rapport n'est écrit en cas d'échec. |
| **Collision de nom de rapport** | Le nom est à la minute (`…-HHMM.md`) : deux analyses terminées dans la même minute s'écrasent. |
| **Qualité d'extraction des PDF** | Les tableaux sont aplatis, les en-têtes et pieds de page polluent les extraits, et un acteur peut être attribué au mauvais rôle. Même constat que dans le [tutoriel 01](01-configuration-open-webui.md#62-choisir-le-bon-format-de-fichier) (section 6.2) : préférer le DOCX. |
| **Débit** | ~14 tokens/s sur la configuration de référence : traitement de fond, pas conversationnel. Une analyse bloque Open WebUI (section 5.4). |
| **Contrôle de confidentialité** | Limité aux termes du dictionnaire (section 8.2). |

### 9.3 Hors périmètre de cette version

- Exposer l'agent dans Open WebUI.
- Un client MCP vers les serveurs du dépôt.
- Un chat conversationnel avec mémoire.
- Un déclenchement automatique au dépôt d'un fichier : *Local File Trigger* est désactivé par défaut dans n8n 2.x.

### 9.4 Pour aller plus loin

- **Router le dépassement de longueur vers le workflow 03** avec un motif contrôlé, pour recevoir un mail explicite au lieu de l'alerte brute.
- **Rendre l'ingestion atomique** : lire les fichiers avant de supprimer la table.
- **Ajouter l'heure à la seconde** (ou un suffixe) au nom du rapport.
- **Traiter un référentiel plus long** en le découpant par sections avant l'extraction des exigences.
- **Évaluer sur un corpus fictif plus large** : le script `evaluate-report.mjs` accepte une autre vérité terrain en second argument.
