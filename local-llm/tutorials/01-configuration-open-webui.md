# Configurer Open WebUI pour un LLM local

Ce tutoriel décrit la configuration d'Open WebUI appliquée à la stack `docker-compose.yml` de ce dépôt (Ollama + Open WebUI + Postgres/pgvector, et n8n en option), et explique **pourquoi** chaque réglage compte sur une machine sans gros GPU dédié.

- **Machines** : toute machine avec Docker (Linux, macOS, Windows avec WSL2). Ollama tourne sur le CPU, ou sur un GPU AMD, Intel ou NVIDIA selon le profil choisi (section 2).
- **Configuration de référence** : les durées et débits cités ont été mesurés sur un Ryzen 7 7840HS avec iGPU Radeon 780M (profil `vulkan`) et 30 Go de RAM. Sur une autre machine, les **ordres de grandeur** changent, pas les réglages : la section 2 explique comment mesurer les vôtres.
- **Modèles** : `granite4.2:8b` (chat, contexte 32k) et `bge-m3` (embeddings)
- **Versions testées** : Open WebUI 0.11.4, Ollama (image `latest`, testée avec le backend Vulkan)
- **Corpus d'exercice** : les deux documents fictifs de `n8n/exemples/` (cahier des charges et proposition du « Projet Héron »), fournis avec le dépôt. Les exemples chiffrés sur des rapports plus volumineux (142 extraits…) viennent du corpus du formateur, qui n'est pas distribué.

### Prérequis

| Élément | Détail |
|---|---|
| Docker | Docker Engine avec le plugin Compose v2 (`docker compose version`), ou Docker Desktop. Sous Windows, Docker Desktop avec le moteur WSL2. |
| Mémoire | 16 Go de RAM au minimum, 32 Go conseillés : la stack complète (Ollama, Open WebUI, n8n, Postgres) et le modèle de chat se partagent la machine. |
| Disque | ~25 Go libres : ~12 Go d'images Docker, ~6,5 Go pour les deux modèles, plus le modèle de code du tutoriel 04. |
| Réseau | Nécessaire au premier démarrage (images et modèles). Ensuite, tout tourne en local. |
| Dépôt | Cloné sur la machine. **Toutes les commandes `docker compose` de ce tutoriel et des suivants se lancent depuis le dossier `local-llm/`**, qui contient `docker-compose.yml` et `.env`. |

---

## 1. Comprendre les contraintes avant de régler quoi que ce soit

Trois faits matériels expliquent tous les choix qui suivent. Ils valent pour toute machine grand public ; seuls les chiffres changent.

| Contrainte | Conséquence |
|---|---|
| La mémoire utilisable par le modèle est limitée : VRAM d'un GPU dédié, mémoire partagée d'un iGPU (~15,8 Go sur la référence), ou RAM en mode CPU | Le modèle de chat et son contexte doivent y tenir (~8 Go pour `granite4.2:8b` à 32k). Un modèle qui déborde du GPU passe en partie sur le CPU et ralentit fortement. Sur un iGPU sous Vulkan, ce partage n'aide même pas : la partie laissée au CPU est aussi réservée dans la mémoire partagée. |
| La génération est limitée par la bande passante mémoire | Un modèle dense de 8B en Q4 (~5 Go) plafonne à **~14,5 tokens/s** sur la référence (DDR5 partagée). Un GPU dédié va plusieurs fois plus vite ; le CPU seul, nettement moins vite. Aucun paramètre logiciel ne dépasse ce plafond. |
| Ollama tourne avec `OLLAMA_NUM_PARALLEL=1` | **Une seule requête à la fois.** Toute requête annexe (titre, tags…) passe *avant* ou *après* la vôtre et la fait attendre. |

Ordres de grandeur mesurés sur la configuration de référence :

- lecture du prompt (*prompt eval*) : **~250 tokens/s** → 1 400 tokens de contexte RAG ≈ 5 s ;
- génération : **~14,5 tokens/s** → une réponse de 600 tokens ≈ 40 s ;
- indexation d'un document de 180 extraits (163 ko de texte) avec `bge-m3` : ~15 s.

> **À retenir** : sur la configuration de référence, chaque token généré coûte ~70 ms. L'essentiel de l'optimisation consiste à **ne pas faire générer de tokens inutiles** au modèle.

### Le symptôme de départ

Une requête avec un document joint ne répondait toujours pas après 5 minutes. Les logs Ollama (`docker compose logs -f ollama`) ont montré deux causes cumulées :

1. **Des tâches d'arrière-plan en file d'attente** : quatre appels d'environ 1 min 50 chacun (titre, tags, suggestions, requêtes de recherche) ont précédé la réponse. Celle-ci n'a démarré qu'au bout de 2 minutes.
2. **Un raisonnement emballé** : `granite4.2:8b` raisonne par défaut (*thinking*). Il avait produit plus de 2 500 tokens de réflexion sans un seul mot de réponse.

Après les réglages ci-dessous, la même requête aboutit en **25 à 45 s**.

---

## 2. Premier démarrage

1. Depuis le dossier `local-llm/`, créer le fichier de configuration : `cp .env.example .env`. Remplacer ensuite chaque `change-me` par une valeur aléatoire, générée par exemple avec `openssl rand -hex 32` (une valeur différente pour chaque secret).

   Le compte administrateur d'Open WebUI se règle aussi dans `.env` :

   | Variable | Effet |
   |---|---|
   | `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` | Compte administrateur créé au premier démarrage ; les inscriptions sont ensuite fermées. Le service `open-webui-init` s'en sert pour appliquer au modèle de base les réglages de la section 3. Laissées vides, le premier compte créé dans l'interface devient administrateur, et toute la configuration de la section 3 se fait à la main. |
   | `OPENWEBUI_EXEMPLES` | `true` : `open-webui-init` crée aussi la base `MBSE Expert` (section 6.1) et l'assistant `Expert MBSE` du [tutoriel 02](02-assistant-workspace-open-webui.md). `false` (défaut) : ces deux exercices restent à faire. |
2. **Adapter la stack à la machine**, dans `.env` :

   | Machine | Ligne à décommenter dans `.env` | Vérification |
   |---|---|---|
   | Linux avec GPU AMD ou Intel (intégré ou dédié) | `COMPOSE_FILE=docker-compose.yml:docker-compose.vulkan.yml` | Reporter dans `RENDER_GID` et `VIDEO_GID` les numéros donnés par `getent group render video`. |
   | Linux ou Windows (WSL2) avec GPU NVIDIA | `COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml` | Le pilote NVIDIA et le *NVIDIA Container Toolkit* doivent être installés (ils sont inclus dans Docker Desktop sous Windows). Sous Windows hors WSL, séparer les fichiers par `;`. |
   | macOS, ou machine sans GPU utilisable | aucune | Ollama tourne sur le CPU. Docker n'a pas accès au GPU d'un Mac. |

   **n8n est optionnel** : il n'est utile qu'à l'agent du [tutoriel 03](03-agent-n8n.md). Pour l'inclure, ajouter `:docker-compose.n8n.yml` à la fin de la ligne `COMPOSE_FILE`, ou décommenter la ligne « + n8n » qui correspond à la machine (sans profil GPU : `COMPOSE_FILE=docker-compose.yml:docker-compose.n8n.yml`). Il peut aussi être ajouté plus tard : un nouveau `docker compose up -d` le démarre.

   **Docling est optionnel** lui aussi : il améliore nettement la lecture des PDF (section 6.2.1), au prix d'une image de 5,1 Go et d'une indexation plus lente. Pour l'inclure, ajouter `:docker-compose.docling.yml` à la fin de la ligne `COMPOSE_FILE`. Il peut être ajouté plus tard.

   Ajuster ensuite la mémoire :

   - le modèle de chat et son contexte doivent tenir dans la mémoire du GPU, ou dans la RAM en mode CPU : ~8 Go pour `granite4.2:8b` à 32k ;
   - avec moins de mémoire, réduire `OLLAMA_CONTEXT_LENGTH` à 16384, ou choisir un modèle plus petit dans `LLM_MODEL` (https://ollama.com/library). Le nom du modèle est alors à remplacer partout où ce tutoriel cite `granite4.2:8b`, et dans `n8n/src/constants.mjs` pour l'agent n8n (tutoriel 03) ;
   - `OLLAMA_MEM_LIMIT` (20 Go par défaut) doit rester inférieur à la RAM de la machine ;
   - si le port 5433 est déjà pris sur l'hôte, changer `POSTGRES_HOST_PORT`.

3. Lancer la stack : `docker compose up -d`.
4. Attendre le téléchargement des modèles. Il n'y a rien à installer à la main : le service `ollama-init` télécharge `LLM_MODEL` et `EMBED_MODEL` (définis dans `.env`) dès qu'Ollama est prêt, puis s'arrête. Au premier lancement, cela représente ~6,5 Go et prend plusieurs minutes. Les lancements suivants sont immédiats, car les modèles restent dans le volume `ollama`.

   ```bash
   docker compose logs -f ollama-init         # progression ; se termine par "success"
   docker compose ps -a ollama-init           # doit afficher "Exited (0)"
   docker compose exec ollama ollama list     # granite4.2:8b et bge-m3 doivent apparaître
   ```

   Si `ollama-init` s'arrête avec un code différent de 0 (coupure réseau, nom de modèle erroné dans `.env`), corriger la cause puis relancer le téléchargement avec `docker compose up ollama-init`.

   Une fois les modèles téléchargés, le service `open-webui-init` configure Open WebUI, puis s'arrête :

   ```bash
   docker compose logs open-webui-init        # "modèle de base granite4.2:8b : réglé", puis la base et l'assistant si OPENWEBUI_EXEMPLES=true
   docker compose ps -a open-webui-init       # doit afficher "Exited (0)"
   ```

   Il peut être relancé à tout moment avec `docker compose up open-webui-init` : il remet le modèle de base aux valeurs de la section 3 (une modification faite entre-temps dans l'interface est alors perdue) et ne recrée pas la base ni l'assistant s'ils existent déjà.

5. Ouvrir http://localhost:3000 et se connecter avec le compte de `.env` (`WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD`). Si ces variables sont vides, créer le compte : **le premier compte créé devient administrateur.** Si la liste des modèles est vide, le téléchargement n'est pas terminé (étape 4) : recharger la page une fois qu'il est fini.

   > **Langue de l'interface** : Open WebUI s'affiche dans la langue du navigateur. Les chemins et les libellés de ces tutoriels sont ceux de l'interface **en anglais** : pour les suivre mot pour mot, choisir *English* dans *Settings → General → Language* (*Paramètres → Général → Langue*).
6. Envoyer un premier message (par exemple « Bonjour ») pour charger le modèle, puis vérifier où il tourne :

   ```bash
   docker compose exec ollama ollama ps
   # PROCESSOR : "100% GPU" avec un profil GPU, "100% CPU" sans profil
   ```

   Ollama ne charge un modèle en mémoire qu'à la première requête. Avant, `ollama ps` affiche une liste vide, ce qui ne veut pas dire que le modèle est absent : c'est `ollama list` qui indique les modèles installés.

   Avec un profil GPU, un affichage `100% CPU` signifie qu'Ollama ne voit pas le GPU : `docker compose logs ollama | grep "inference compute"` doit citer le GPU (par exemple `library=Vulkan` ou `library=CUDA`). Un partage comme `40%/60% CPU/GPU` signifie que le modèle ne tient pas en mémoire GPU : réduire le contexte ou changer de modèle.

7. Mesurer les débits de **votre** machine, qui serviront de repère à la place de ceux de la configuration de référence :

   ```bash
   docker compose exec ollama ollama run granite4.2:8b --verbose "Explique le RAG en trois phrases."
   # eval rate        : vitesse de génération (~14,5 tokens/s sur la référence)
   # prompt eval rate : vitesse de lecture du prompt, peu significative ici (voir ci-dessous)
   ```

   Sur un prompt aussi court (une vingtaine de tokens), le *prompt eval rate* affiché est bas (~70 tokens/s sur la référence) et ne mesure pas la vraie vitesse de lecture. Celle-ci se lit sur une requête avec un document joint, dans les logs d'Ollama (section 8) : ~250 tokens/s sur la référence.

   Plus la génération est lente, plus les réglages des sections 3 et 4 comptent. En mode CPU, elle peut descendre à quelques tokens/s : préférer alors un modèle plus petit.

> ⚠️ **PersistentConfig** : au premier démarrage, Open WebUI copie les variables d'environnement (`RAG_TOP_K`, `CHUNK_SIZE`…) dans sa base (`webui.db`). Ensuite, **c'est la base qui fait foi**. Modifier `docker-compose.yml` n'a plus d'effet sur ces réglages : il faut passer par l'interface d'administration.
>
> `docker-compose.yml` fixe déjà, par ces variables, les réglages des sections 4 et 5. Sur une installation neuve, ces sections servent donc à **comprendre et vérifier** les valeurs, pas à les saisir. Une installation antérieure garde ses anciennes valeurs : il faut les reporter à la main, ou repartir de zéro en supprimant le volume d'Open WebUI (`docker compose down`, puis `docker volume rm local-llm_openwebui` ; les conversations, comptes et bases de connaissances sont alors perdus).

---

## 3. Réglages du modèle

**Chemin** : *Admin Panel → Settings → Models → granite4.2:8b* (icône crayon)

*Admin Panel* se trouve dans le menu de l'avatar, en bas à gauche. Son onglet *Settings* ouvre une fenêtre dont la colonne de gauche regroupe, sous **Admin**, les sections *System*, *AI* (dont *Models*), *Experience* (dont *Interface*) et *Tools* (dont *Documents*). Les chemins de ce tutoriel désignent ces entrées.

Ces réglages s'appliquent à toutes les conversations qui utilisent ce modèle. Ils sont enregistrés dans la base d'Open WebUI et non dans Ollama.

> Avec un compte administrateur défini dans `.env` (section 2), `open-webui-init` a déjà appliqué les valeurs des sections 3.1 et 3.2 : ouvrir l'écran pour les vérifier.

### 3.1 Advanced Params

Cliquer sur **Show** à droite de *Advanced Params* pour afficher la liste. Chaque paramètre affiche *Default* tant qu'on ne clique pas dessus. Un clic sur *Default* fait défiler les valeurs possibles : pour **think (Ollama)**, *On*, puis *Custom*, puis **Off** (trois clics) ; pour *max_tokens* et *Temperature*, un clic affiche *Custom* et un champ où saisir la valeur.

| Paramètre | Valeur | Ce que ça implique |
|---|---|---|
| **think (Ollama)** | **Off** | Désactive la phase de réflexion du modèle. C'est le réglage le plus important : avec *thinking* actif, le modèle peut produire des milliers de tokens invisibles avant de répondre, soit plusieurs minutes à 14 tokens/s. On perd un peu en qualité sur les raisonnements complexes (logique, calcul), mais pas sur la synthèse documentaire. Pour un besoin ponctuel, on peut le réactiver dans les contrôles d'une conversation. |
| **max_tokens** | **2048** | Longueur maximale d'une réponse (transmis à Ollama sous le nom `num_predict`). C'est un garde-fou : si le modèle s'emballe ou boucle, la génération s'arrête au bout de ~2 min 20 au lieu de remplir les 32k de contexte. 2 048 tokens représentent environ 1 500 mots, ce qui suffit pour une réponse détaillée. À augmenter si les réponses longues sont coupées. |
| **Temperature** | **0.3** | Degré d'aléatoire dans le choix des mots. La valeur par défaut du modèle est 1, ce qui favorise la créativité mais aussi les digressions et les répétitions. Pour du RAG et de l'analyse technique, une valeur basse produit des réponses plus fidèles au document et plus reproductibles. Remonter vers 0.7–0.9 pour de la rédaction créative. |
| **Function Calling** | **Native** | Mode d'appel des outils. En *Native*, le modèle utilise son propre format d'appel d'outils (granite le supporte). En *Default*, Open WebUI simule l'appel d'outils par un prompt supplémentaire. Le mode *Native* est plus fiable pour les agents, à condition de limiter le nombre d'outils exposés (voir 3.2). |
| **num_ctx (Ollama)** | *Default* | Taille du contexte. Laisser sur *Default* : elle est déjà fixée à 32 768 par `OLLAMA_CONTEXT_LENGTH` dans `.env`. Si on la change ici, Ollama doit recharger le modèle avec une autre taille de cache, ce qui coûte ~10 s à chaque changement. |
| **keep_alive (Ollama)** | *Default* | Durée pendant laquelle le modèle reste en mémoire après usage. Elle est déjà fixée à 30 min par `OLLAMA_KEEP_ALIVE`. |

Les autres paramètres (`top_k`, `top_p`, `repeat_penalty`, `mirostat`…) restent sur *Default* : les valeurs fournies avec le modèle conviennent.

### 3.2 Capabilities et Builtin Tools

Plus bas sur la même page.

**Capabilities** : elles indiquent à l'interface ce que le modèle sait faire et affichent les boutons correspondants.

| Capability | Valeur | Raison |
|---|---|---|
| File Upload, File Context | ✅ | Indispensables pour joindre des documents et en injecter le contenu. |
| Citations | ✅ | Affiche les extraits sources sous la réponse, ce qui permet de vérifier ce que le modèle a lu. |
| Status Updates | ✅ | Affiche l'avancement (« recherche dans les documents… »), utile vu les temps de réponse. |
| Vision | ❌ | `granite4.2:8b` ne lit pas les images. Une image jointe serait ignorée ou provoquerait une erreur. |
| Web Search, Image Generation, Code Interpreter, Terminal | ❌ | Aucun de ces services n'est configuré dans la stack. Les laisser actifs propose des fonctions qui échoueraient. |
| Usage, Memory | inchangés | *Usage* affiche les compteurs de tokens. *Memory* est expliquée au [tutoriel 02, §9.2](02-assistant-workspace-open-webui.md#92-memory). |

**Builtin Tools** : ❌ **décoché**.

En mode *Function Calling: Native*, chaque outil intégré activé (mémoire, notes, calendrier, base de connaissances…) est **décrit dans le prompt de chaque requête**. Cela a trois conséquences :

- **le prompt s'allonge** et chaque message coûte plusieurs secondes de lecture supplémentaires ;
- **un modèle de 8B se disperse** face à une quinzaine d'outils et en appelle d'inutiles, ce qui ajoute à chaque fois un aller-retour complet ;
- **avec les outils *Files* et *Knowledge Base* actifs**, Open WebUI peut laisser au modèle le soin d'aller lire le document par un appel d'outil au lieu d'injecter directement les extraits. Un petit modèle oublie souvent de le faire et répond sans avoir lu le document.

Builtin Tools désactivé, les fichiers joints à la conversation et les bases appelées par `#` passent par le RAG classique : Open WebUI recherche lui-même les extraits pertinents et les place dans le prompt.

> ⚠️ Ce n'est **pas** le cas d'une base **rattachée à un assistant** du Workspace. En mode Native, celle-ci n'est consultable que par l'outil intégré `query_knowledge_files`. Un assistant documentaire doit donc passer en *Function Calling: Legacy*. Voir [Créer un assistant dans le Workspace, §5.4](02-assistant-workspace-open-webui.md#54-le-choix-décisif--legacy-ou-native).

### 3.3 System Prompt

> **Où le mettre** : laissez le System Prompt du **modèle de base vide**. Une consigne comme « answer only from the provided context » s'appliquerait à toutes les conversations, et le modèle refuserait les questions générales. Placez-la dans un **assistant** du Workspace (*Workspace → Models*), comme décrit dans [Créer un assistant dans le Workspace](02-assistant-workspace-open-webui.md). Le texte et son explication ci-dessous restent valables.

Prompt utilisé pour l'assistant documentaire :

```text
You are an MBSE expert. Answer only from the provided context. When the context
lists items (deliverables, risks, work packages), list all of them. If the
information is missing, say so explicitly. Cite sources as [n] and never mention
source tags.
```

Ce texte est ajouté au début de chaque conversation. Chaque consigne corrige un défaut observé pendant les tests :

| Consigne | Défaut corrigé |
|---|---|
| *Answer only from the provided context* | Sans cette consigne, le modèle complète avec ses propres connaissances, et on ne distingue plus ce qui vient des documents de ce qui est inventé. |
| *List all of them* | Un petit modèle a tendance à résumer une liste au lieu de l'énumérer, et oublie alors des éléments. |
| *If the information is missing, say so* | Encourage le modèle à avouer qu'il ne sait pas plutôt qu'à halluciner. Sans cette consigne, c'est le premier risque d'un RAG. |
| *Cite sources as [n], never mention source tags* | Open WebUI encadre les extraits par des balises `<source id="…">`. Le modèle avait tendance à les recopier dans sa réponse (« based on `<source id="2">`… »). |

Adapter le rôle (« MBSE expert ») au domaine des documents. La consigne est en anglais parce que les documents d'origine l'étaient ; elle fonctionne aussi sur le corpus fictif en français. Le modèle répond en général dans la langue de la question, sauf quand il signale une information absente : mesuré sur le corpus fictif, cet aveu arrive en anglais, même en ajoutant « in the language of the question » à la consigne. Pour des réponses toujours en français, traduire la consigne.

Valider avec **Save & Update**.

---

## 4. Tâches d'arrière-plan

**Chemin** : *Admin Panel → Settings → **Admin › Experience › Interface*** → section **Tasks**

> Attention à ne pas confondre avec *Personal › Interface* (en haut du menu), qui ne contient que les préférences d'affichage de l'utilisateur.

Ces valeurs sont fixées par `docker-compose.yml` (variables `ENABLE_*_GENERATION`) sur une installation neuve.

Open WebUI utilise le modèle de chat pour de petites tâches automatiques. Avec une seule requête traitée à la fois, **chacune bloque le GPU** : avant la réponse, elle retarde son démarrage ; après, elle retarde la question suivante.

| Tâche | Valeur | Coût mesuré | Ce que ça implique |
|---|---|---|---|
| **Follow Up Generation** | **Off** | ~14 s après chaque réponse | Propose des questions de relance cliquables. Agréable, mais c'est la tâche la plus coûteuse : ~150 tokens générés à chaque réponse. |
| **Tags Generation** | **Off** | ~5 s | Classe automatiquement les conversations par mots-clés. Peu utile pour un usage individuel. |
| **Title Generation** | Off *(ou On)* | ~5 s | Donne un titre à la conversation au premier échange. Coût faible (~20 tokens) : c'est une question de confort. Désactivé, le titre reprend le début du premier message. |
| **Retrieval Query Generation** | **On** | ~5–7 s avant la réponse | Avant de chercher dans les documents, le modèle reformule la question en requêtes de recherche. C'est utile en conversation : « et pour le niveau L3 ? » devient une requête autonome sur le bon sujet. À désactiver si on pose toujours des questions complètes et qu'on veut gagner quelques secondes. |
| **Web Search Query Generation** | **Off** | — | Sert uniquement à la recherche web, qui n'est pas configurée. |
| **Autocomplete Generation** | **Off** | à chaque frappe | Propose des complétions pendant la saisie. Rédhibitoire sur un modèle local lent : chaque pause dans la frappe lance une génération. |

**Task Model** : on peut y désigner un modèle plus petit et plus rapide dédié à ces tâches. Ici on garde *Current Model*, car charger un second modèle de chat réduirait la mémoire disponible pour le modèle principal.

Valider avec **Save**.

---

## 5. Documents et RAG

**Chemin** : *Admin Panel → Settings → Tools › Documents*

Sur une installation neuve, ces valeurs viennent de `docker-compose.yml`.

| Paramètre | Valeur | Ce que ça implique |
|---|---|---|
| **Embedding Model Engine / Model** | Ollama / `bge-m3` | Modèle multilingue (FR/EN) qui transforme chaque extrait en vecteur. Il tourne dans Ollama (sur le GPU si un profil GPU est actif) et reste chargé à côté du modèle de chat (`OLLAMA_MAX_LOADED_MODELS=2`). |
| **Embedding Batch Size** | **32** | Nombre d'extraits envoyés en une fois au modèle d'embedding. À 1 (valeur par défaut d'Open WebUI), un document de 180 extraits fait 180 appels à Ollama ; à 32, il en fait 6. Sur la configuration de référence, la durée ne change presque pas (~15 s dans les deux cas) : c'est le calcul des vecteurs qui domine. Le réglage allège le trafic vers Ollama, sans effet sur la qualité. |
| **Concurrent Requests** | **2** | Nombre d'appels d'embedding lancés en même temps (*Async Embedding Processing* actif). À 0 (valeur par défaut d'Open WebUI), il n'y a aucune limite : avec des lots de 1, un PDF de plus de ~1 000 extraits ouvre autant de connexions simultanées et dépasse la limite de 1 024 fichiers ouverts du conteneur. L'indexation échoue alors avec `Cannot connect to host ollama:11434 ssl:default [Too many open files]`. Plus de parallélisme n'accélère rien : Ollama traite une requête à la fois. |
| *Base vectorielle* | pgvector (`rag`) | Fixée par `docker-compose.yml` (`VECTOR_DB`), elle n'apparaît pas dans cet écran. Les vecteurs sont stockés dans Postgres (table `document_chunk`), dans la même base `rag` que ceux de n8n. |
| **Chunk Size / Overlap** | 1000 / 150 | Taille des extraits en caractères (~250 tokens) et chevauchement entre deux extraits consécutifs. Des extraits plus petits rendent la recherche plus précise mais donnent moins de contexte. Le chevauchement évite de couper une idée en deux. |
| **Markdown Header Text Splitter** | On | Découpe d'abord le document selon ses titres, puis selon la taille. Les extraits respectent ainsi la structure (sections, sous-sections). |
| **Hybrid Search** | On | Combine la recherche par mots-clés (BM25) et la recherche sémantique (vecteurs). Le BM25 retrouve les termes exacts (acronymes, références comme « SysML v2 » ou « §4.2 »), là où la recherche sémantique seule échoue souvent sur du contenu technique. |
| **Top K** | **8** | Nombre d'extraits injectés dans le prompt. À 5 (~1 250 tokens), une question sur les livrables d'un cahier des charges a oublié le principal : le tableau des livrables était coupé en deux extraits, et un des 5 extraits était occupé par la table des matières. À 8 (~2 000 tokens), il faut compter ~4 s de lecture en plus par question, contre une bien meilleure couverture des listes et des tableaux. Au-delà de 10, le gain diminue et un modèle de 8B se perd dans trop de contexte. |
| **Top K Reranker** | **8** (comme Top K) | ⚠️ **Indispensable avec Hybrid Search.** En recherche hybride, Open WebUI ne garde que les *Top K Reranker* meilleurs extraits, même sans modèle de reranking : le nombre d'extraits transmis est le plus petit des deux réglages. Avec la valeur par défaut (3), *Top K = 8* n'a aucun effet et le modèle ne reçoit que 3 extraits. Mesuré sur le corpus fictif : avec 3 extraits, « Que demande l'exigence EX-04 ? » a reçu la réponse de l'exigence EX-05 ; avec 8, la bonne réponse. |
| **Relevance Threshold** | 0 | Aucun filtrage par score : les 8 meilleurs extraits sont toujours transmis. |

### Limite du RAG : questions ciblées ou résumé global

Le RAG ne transmet au modèle que les **8 extraits les plus pertinents** (Top K), par exemple 8 sur les 142 d'un rapport.

- ✅ **Questions ciblées** (« que recommande le rapport pour les profils L2 et L3 ? ») : c'est le cas d'usage idéal.
- ⚠️ **Résumé global** (« résume ce document ») : le modèle ne voit qu'environ 6 % du texte et le résumé sera partiel.

Pour un résumé, cliquer sur le fichier joint à la conversation : sa fenêtre affiche un interrupteur *Using Focused Retrieval* (le RAG) ; l'activer le fait passer à **Using Entire Document**. Le contenu complet est alors injecté, à deux conditions :

- **le document doit tenir dans le contexte de 32k tokens**, soit ~100 pages de texte dense ;
- **il faut accepter la lecture du prompt** : ~2 minutes pour 30 000 tokens à ~250 tokens/s sur la configuration de référence.

Pour les gros documents, préférer un résumé section par section, ou un workflow n8n de résumé progressif.

---

## 6. Créer une base de connaissances

Joindre un fichier à une conversation l'indexe **pour cette conversation seulement**. Pour un corpus qu'on interroge régulièrement, on crée une base de connaissances : les documents y sont indexés une seule fois, et on peut l'interroger depuis n'importe quelle conversation.

### 6.1 Création

1. **Workspace** → onglet **Knowledge** → bouton **Create** en haut à droite.

   > Le bouton *Create* crée l'élément de l'onglet affiché. Sur l'onglet *Models*, il crée un modèle, pas une base.

2. Renseigner un **nom** et une **description**. La description est visible par le modèle et l'aide à savoir quand s'en servir : décrire le contenu plutôt que l'usage. Pour l'exercice : nom `MBSE Expert`, description « Cahier des charges et proposition technique du Projet Héron : migration SysML v1 vers SysML v2 chez Acme Défense ».
3. Ajouter les documents par glisser-déposer et attendre la fin de l'indexation de chacun. Pour l'exercice, ajouter les deux fichiers du dossier `local-llm/n8n/exemples/` : `sow-exemple.md` et `Proposition – Projet Héron, v2.md` (pas `verite-terrain.json`, qui sert au tutoriel 03). Sur la configuration de référence, un document de 180 extraits est indexé en ~15 s ; les deux documents fictifs, très courts, le sont en quelques secondes.

   > Avec `OPENWEBUI_EXEMPLES=true` (section 2), `open-webui-init` a déjà créé cette base avec les deux documents : il suffit de l'ouvrir pour vérifier les étapes ci-dessus.

   > Le corpus fictif compte 13 extraits (4 pour le cahier des charges, 9 pour la proposition : le découpage par titres Markdown crée un extrait par section). Top K en transmet 8, soit plus de la moitié : les limites du RAG décrites en section 5 n'apparaissent vraiment qu'avec des documents plus longs. Refaire l'exercice avec vos propres documents pour les observer.

### 6.2 Choisir le bon format de fichier

Tous les formats ne se valent pas. La qualité des réponses dépend d'abord de la qualité de l'extraction du texte.

| Format | Qualité | Pourquoi |
|---|---|---|
| **DOCX, Markdown** | ✅ Bonne | Les titres sont reconnus : le découpage suit les sections. Les tableaux gardent leurs lignes et leurs colonnes. |
| **PDF**, extracteur intégré | ⚠️ Moyenne | Le texte est extrait page par page, sans structure. **Les tableaux sont aplatis** et leurs colonnes se mélangent. La **table des matières** et les **pieds de page** (mentions de copyright…) deviennent des extraits à part entière, qui encombrent la recherche. |
| **PDF**, avec Docling (6.2.1) | ✅ Bonne | La mise en page est analysée : tableaux restitués en tableaux Markdown, en-têtes et pieds de page écartés, titres reconnus (le découpage suit les sections). La table des matières reste un extrait. |
| PDF scanné | ❌ | Aucun texte sans OCR. Docling sait le faire, mais l'OCR est désactivé par défaut (6.2.1). |

Exemple observé : dans un tableau comparatif extrait d'un PDF, le modèle a attribué à Acme Défense une classification qui appartenait à une autre organisation, parce que les colonnes étaient mélangées.

> **Règle pratique** : quand un document existe en DOCX et en PDF, indexer le DOCX. Sans DOCX, activer Docling (6.2.1) avant d'indexer des PDF qui contiennent des tableaux.

#### 6.2.1 Activer Docling pour les PDF

[Docling](https://github.com/docling-project/docling-serve) convertit chaque document en Markdown en analysant sa mise en page. Une fois activé, Open WebUI lui envoie tous les fichiers déposés, sauf le Markdown et le texte brut qu'il lit lui-même : les PDF, mais aussi les DOCX, PPTX et XLSX.

**Coût**, mesuré sur la configuration de référence :

| | |
|---|---|
| Image Docker | 5,1 Go à télécharger une fois |
| Mémoire | ~0,8 Go au repos, jusqu'à ~3,3 Go pendant la conversion d'un long PDF (plafond : `DOCLING_MEM_LIMIT` dans `.env`, 6 Go par défaut) |
| Démarrage | ~10 s avant qu'Open WebUI ne démarre |
| Conversion | ~0,5 s par page : 1 min 30 s pour un PDF de 182 pages ; 8 s au lieu de 2 s pour indexer le PDF d'exemple de 3 pages |

L'indexation d'un PDF est donc nettement plus lente qu'avec l'extracteur intégré : c'est le prix de la structure.

**Activer** : ajouter `:docker-compose.docling.yml` à la fin de la ligne `COMPOSE_FILE` de `.env`, puis :

```bash
docker compose up -d
docker compose ps docling                  # doit afficher "(healthy)"
docker compose logs open-webui-init        # "extraction des documents : Docling (réglé)"
```

Open WebUI ne lit ses variables d'extraction qu'au premier démarrage (PersistentConfig, section 2) : c'est donc `open-webui-init` qui bascule une installation existante sur Docling. Le réglage est visible dans *Admin Panel → Settings → Documents → Content Extraction Engine*. Les documents déjà indexés ne sont pas reconvertis : pour en profiter, les retirer de la base et les ajouter à nouveau.

> **Sans compte administrateur dans `.env`** (`WEBUI_ADMIN_EMAIL` vide), `open-webui-init` ne règle rien, et la bascule est à faire à la main sur une installation existante, à l'activation comme au retrait : *Admin Panel → Settings → Documents → Content Extraction Engine*, `Docling` avec l'URL `http://docling:5001`, ou retour à `Default`. Sinon, après un retrait, chaque dépôt de PDF ou de DOCX échoue.

**Désactiver** : retirer `:docker-compose.docling.yml` de `COMPOSE_FILE`, puis `docker compose up -d --remove-orphans`. `open-webui-init` affiche alors « extraction des documents : extracteur intégré (Docling retiré) ». Sans cette bascule, Open WebUI continuerait d'envoyer les fichiers à un service arrêté, et chaque dépôt échouerait.

> Comme pour le modèle de base, relancer `open-webui-init` remet le moteur d'extraction aux valeurs de l'overlay. Un autre moteur choisi à la main dans l'interface (Tika, par exemple) n'est conservé que si l'overlay n'est pas chargé.

**PDF scannés (OCR)** : l'OCR est désactivé, car il ne sert qu'aux PDF sans texte et multiplie le temps de conversion (6 s au lieu de 2 s pour 3 pages sur la configuration de référence). Pour l'activer, remplacer `"do_ocr": "false"` par `"do_ocr": "true"` dans `docker-compose.docling.yml` (variable `DOCLING_PARAMS`), puis `docker compose up -d`.

**Exercice : comparer les deux extracteurs.** Le PDF fictif `open-webui/exemples/matrice-acteurs-heron.pdf` contient un sommaire, un pied de page répété et un tableau dont certaines cellules sont vides ou tiennent sur plusieurs lignes. Le joindre à une conversation (bouton **+** → *Upload Files*), une fois sans Docling et une fois avec, et poser les mêmes questions :

| Question | Réponse attendue |
|---|---|
| « Quelle classification des données s'applique à Kerlan Ingénierie ? » | Aucune n'est indiquée (cellule vide). |
| « Quel accès au référentiel SysML a Orbitec Systèmes ? » | Aucun n'est indiqué (cellule vide). |
| « Quelles organisations ont un accès en lecture seule au référentiel SysML ? » | Bureau Vertex et Kerlan Ingénierie. |
| « Qui relit le plan de migration, et quelle est son échéance ? » | Bureau Vertex, mois 6. |

Observé sur la configuration de référence (deux essais par extracteur) :

- **sans Docling**, le PDF donne 3 extraits, un par page, qui commencent tous par le pied de page. Le tableau est aplati, une cellule par ligne : une cellule vide ne laisse aucune trace. Le modèle répond donc « lecture seule » pour la classification de Kerlan Ingénierie et « en attente » pour l'accès d'Orbitec Systèmes, aux deux essais, en prenant la valeur de la colonne voisine. La question 3 n'est réussie qu'une fois sur deux (l'autre réponse s'emballe et ne conclut pas) ; la question 4 est réussie ;
- **avec Docling**, le PDF donne 7 extraits, un par section, sans pied de page, et les tableaux restent des tableaux. Les questions 1, 3 et 4 sont réussies aux deux essais. À la question 2, la conclusion est juste (accès non indiqué), mais un essai affirme à tort qu'Orbitec Systèmes ne figure pas dans le tableau : voir la deuxième limite ci-dessous.

Pour voir la différence à la source, compter dans `document_chunk` (section 6.4) les extraits qui contiennent le pied de page :

```bash
docker compose exec postgres psql -U n8n -d rag -c "
  SELECT collection_name, count(*) AS extraits,
         count(*) FILTER (WHERE text ILIKE '%Diffusion restreinte%') AS avec_pied_de_page
  FROM document_chunk WHERE vmetadata->>'name' = 'matrice-acteurs-heron.pdf' GROUP BY 1;"
```

**Limites** : Docling n'est pas infaillible.

- Une cellule dont le texte touche presque le bord de sa colonne peut déborder sur la cellule voisine. Dans le PDF d'exemple, la première ligne du tableau des livrables sort ainsi en `Rapport d'inventaire des modèlesEX-01`, avec une colonne *Exigence* vide.
- Docling aligne les colonnes de ses tableaux avec des espaces. Un tableau de plus de quelques lignes dépasse donc vite la taille d'un extrait (`CHUNK_SIZE`, 1 000 caractères, section 5) et se retrouve coupé : seul le premier morceau porte la ligne d'en-tête. Le modèle reçoit alors des lignes sans le nom des colonnes.

**Dépannage**

| Symptôme | Cause | Remède |
|---|---|---|
| L'indexation d'un long PDF échoue au bout de 30 min ; `docker compose logs docling` cite `DOCLING_SERVE_MAX_SYNC_WAIT` | Conversion plus longue que le délai de Docling (30 min) | Relever `DOCLING_SERVE_MAX_SYNC_WAIT` dans `docker-compose.docling.yml`, ou découper le document. |
| Tout dépôt de PDF ou de DOCX échoue aussitôt | Docling arrêté ou pas encore prêt | `docker compose ps docling`, puis `docker compose logs docling`. Si l'overlay a été retiré, relancer `docker compose up open-webui-init`, ou, sans compte administrateur dans `.env`, remettre *Content Extraction Engine* à `Default` à la main. |
| Le conteneur `docling` redémarre pendant une conversion | Mémoire insuffisante (conteneur tué) | Relever `DOCLING_MEM_LIMIT` dans `.env`, sans dépasser la RAM disponible. |
| `open-webui-init` s'arrête sur « DOCLING_PARAMS n'est pas du JSON valide » | Faute de frappe dans `docker-compose.docling.yml` | Corriger la valeur : un objet JSON, guillemets doubles. |

### 6.3 Interroger la base

- **Ponctuellement** : dans une conversation, taper `#` puis choisir la base.
- **En permanence** : créer un assistant (par exemple « Expert MBSE ») dans *Workspace → Models*, avec la base rattachée, un prompt système dédié et *Function Calling* en **Legacy**. Voir [Créer un assistant dans le Workspace](02-assistant-workspace-open-webui.md).

### 6.4 Contrôler l'indexation

Les extraits sont stockés dans la table `document_chunk` de la base `rag`. La colonne `collection_name` contient :

- l'identifiant de la base de connaissances, pour ses documents ;
- `file-<id>` pour chaque fichier, qu'il soit joint à une conversation ou ajouté à une base : un document d'une base est donc indexé deux fois, une fois dans sa propre collection et une fois dans celle de la base ;
- `knowledge-bases`, qui contient une entrée par base (nom et description), pour retrouver les bases elles-mêmes.

```bash
docker compose exec postgres psql -U n8n -d rag -c "
  SELECT collection_name, vmetadata->>'name' AS fichier, count(*) AS extraits
  FROM document_chunk GROUP BY 1, 2 ORDER BY 1;"
```

`n8n` est l'utilisateur Postgres par défaut (`POSTGRES_USER` dans `.env`) : remplacer cette valeur si vous l'avez changée.

Pour vérifier qu'un passage précis a été correctement extrait :

```bash
docker compose exec postgres psql -U n8n -d rag -c "
  SELECT vmetadata->>'page', left(text, 300) FROM document_chunk
  WHERE text ILIKE '%livrable%' LIMIT 5;"
```

À noter : les fichiers joints aux conversations restent indexés dans leur propre collection même après la fin de la conversation.

---

## 7. Tester le RAG

Une réponse qui « a l'air bonne » ne suffit pas : il faut vérifier qu'elle est **complète** et **fidèle**. Pour cela, poser une série de questions qui testent chacune un aspect différent, et **cliquer sur les citations** sous chaque réponse pour lire les extraits transmis au modèle.

Les exemples portent sur la base `MBSE Expert` créée en 6.1 avec le corpus fictif. Dans une conversation avec `granite4.2:8b`, taper `#`, choisir la base, puis poser la question.

| # | Type de question | Exemple | Réponse attendue | Ce qu'on vérifie |
|---|---|---|---|---|
| 1 | Un fait précis, dans un seul document | « Quels livrables le cahier des charges demande-t-il ? » | Quatre : rapport d'inventaire (EX-01), plan de migration (EX-05), rapport final (EX-08), guide de modélisation mis à jour (EX-10). | La recherche trouve le bon passage, et la liste est complète. |
| 2 | Un terme exact (référence, nom propre) | « Que demande l'exigence EX-04 ? » | Une formation de deux jours pour douze ingénieurs. | La recherche par mots-clés (BM25) fonctionne. |
| 3 | Une question qui demande plusieurs documents | « La proposition de Novaltis couvre-t-elle l'exigence EX-04 ? » | Partiellement : la proposition prévoit une seule journée au lieu de deux. | La recherche rapporte des extraits des deux documents. |
| 4 | Une relance | après la 3 : « et l'exigence EX-09 ? » | Non couverte : la proposition ne mentionne aucun support après le projet. | La reformulation de la question (*Retrieval Query Generation*). |
| 5 | **Une information absente des documents** | « Quel est le coût de licence par poste ? » | Le modèle dit que l'information ne figure pas dans les documents. | **C'est le test le plus important.** |

Un petit modèle ne réussit pas toujours les cinq du premier coup : c'est justement ce que le tableau suivant aide à diagnostiquer.

Mesuré sur la configuration de référence, avec les réglages de ce tutoriel (deux séries) :

- les questions 1, 2 et 5 sont réussies ;
- la question 3 est manquée à chaque essai : le modèle répond « oui » en citant l'exigence du cahier des charges (deux jours) comme si elle venait de la proposition. L'extrait de la proposition (« une journée ») figure pourtant dans les citations : c'est le cas « l'élément est dans une citation mais pas dans la réponse » du tableau ci-dessous ;
- la relance 4 s'emballe : la bonne réponse (« non couverte ») arrive, puis le modèle commente ses propres citations jusqu'à la limite `max_tokens` (2 048 tokens, ~2 min 30 s). C'est le garde-fou de la section 3.1 qui l'arrête.

Comparer deux documents exigence par exigence dépasse ce qu'un modèle de 8B fait de façon fiable en une seule réponse : c'est le rôle de l'agent n8n du [tutoriel 03](03-agent-n8n.md), qui traite une exigence à la fois et obtient 10 verdicts justes sur 10 sur ce corpus.

### Diagnostiquer une mauvaise réponse

Toujours comparer la réponse aux citations. L'origine du problème est souvent dans la recherche, pas dans le modèle.

| Constat | Cause | Remède |
|---|---|---|
| Un élément manque, et il n'apparaît dans **aucune** citation | La recherche ne l'a pas trouvé (extrait coupé, Top K trop faible). | Augmenter Top K, reformuler la question avec les termes exacts du document. |
| L'élément est **dans** une citation mais pas dans la réponse | Le modèle a résumé au lieu d'énumérer. | Renforcer le prompt système (« list all of them »). |
| Une citation pointe vers une table des matières ou un pied de page | Bruit d'extraction du PDF. | Indexer le DOCX à la place. Docling (6.2.1) écarte les pieds de page, pas la table des matières. |
| Une information est attribuée au mauvais acteur | Tableau aplati par l'extraction PDF. | Indexer le DOCX, activer Docling (6.2.1), ou interroger la section concernée directement. |
| Une réponse précise sur un sujet absent des documents | Hallucination. | Vérifier le prompt système (« answer only from the provided context »). |

---

## 8. Vérifier que tout fonctionne

Suivre les logs pendant une requête :

```bash
docker compose logs -f ollama | grep -E 'POST|new prompt|prompt eval|eval time'
```

Ce qu'on doit observer pour une question avec un document joint (durées de la configuration de référence) :

```text
| 200 |  3.71s | 172.29.0.4 | POST "/api/chat"     ← reformulation de la question (Retrieval Query Generation)
new prompt, n_ctx_slot = 32768, ... task.n_tokens = 998        ← consignes RAG + question + extraits
prompt eval time =  3951.56 ms /   998 tokens (... 252.56 tokens per second)
       eval time = 16254.06 ms /   235 tokens (... 14.40 tokens per second)
| 200 | 20.23s | 172.29.0.4 | POST "/api/chat"     ← la réponse
```

Les lignes réelles sont plus longues (horodatage, identifiants de tâche) ; seules les parties utiles sont reproduites. Les lignes `new prompt` avec `n_ctx_slot = 8192` et les `POST "/api/embed"` viennent de `bge-m3`, qui calcule les vecteurs de la question et des documents.

Signes d'un problème :

| Observation | Cause probable |
|---|---|
| `task.n_tokens` de quelques dizaines seulement (la question seule) avec un document joint ; avec le corpus fictif, une question normale en compte 300 à 1 000 | Les extraits ne sont pas injectés : vérifier *Builtin Tools* (3.2) et, pour un assistant, le mode *Function Calling* (Legacy). |
| Plusieurs `POST /api/chat` avant que la réponse ne s'affiche | Des tâches d'arrière-plan sont encore actives (section 4). |
| Génération longue avec une réponse vide à l'écran | *think* n'est pas désactivé (3.1). |
| `ollama ps` affiche un pourcentage de CPU alors qu'un profil GPU est actif | Le modèle ne tient pas en mémoire GPU, ou le GPU n'est pas détecté : voir la section 2, étape 6. |

---

## 9. Récapitulatif

| Où | Réglage | Valeur |
|---|---|---|
| Models → Advanced Params | think (Ollama) | Off |
| | max_tokens | 2048 |
| | Temperature | 0.3 |
| | Function Calling | Native |
| Models → System Prompt | modèle de base | vide (consignes RAG dans l'assistant, 3.3) |
| Models → Capabilities | Vision, Web Search, Image Gen., Code Interpreter, Terminal | décochés |
| | Builtin Tools | décoché |
| Admin › Interface → Tasks | Follow Up, Tags, Web Search Query, Autocomplete | Off |
| | Retrieval Query Generation | On |
| | Title Generation | au choix |
| Admin › Documents | Embedding Batch Size | 32 |
| | Concurrent Requests | 2 (sinon « Too many open files » sur un gros document) |
| | Top K | 8 |
| | Top K Reranker | 8 (sinon 3 extraits seulement en recherche hybride) |
| Workspace › Knowledge | documents | DOCX de préférence au PDF, ou PDF avec Docling (6.2.1) |

Sur une installation neuve, les lignes *Interface* et *Documents* viennent de `docker-compose.yml`, et les lignes *Models* de `open-webui-init` si un compte administrateur est défini dans `.env`.

**Résultat** sur la configuration de référence : une question sur un document passe de plus de 5 minutes (sans aboutir) à **25–45 secondes** selon la longueur de la réponse, et Ollama est libre dès la fin de la réponse.

### Pour aller plus loin

- **Gagner en vitesse de génération** : seul un modèle *Mixture of Experts* (par exemple `granite4:tiny-h`, ~1B paramètres actifs par token) peut dépasser le plafond de génération d'un modèle dense (~14,5 tokens/s sur la référence), au prix d'un raisonnement moins solide.
- **Améliorer le classement des extraits** : un modèle de *reranking* (par exemple `bge-reranker-v2-m3`) reclasse les extraits trouvés avant de les envoyer au modèle. La pertinence s'améliore, mais le calcul se fait sur le CPU du conteneur Open WebUI et ajoute quelques secondes par question.
- **Nettoyer pgvector** : supprimer les fichiers d'essai dans *Settings → Data Controls → Manage Files* ; Open WebUI efface alors aussi leur collection `file-*` (vérifié avec la requête de 6.4). Éviter de les supprimer directement en SQL : une collection `file-*` peut appartenir à un document d'une base (6.4).
