# Configurer Open WebUI pour un LLM local sur iGPU (Radeon 780M)

Ce tutoriel décrit la configuration d'Open WebUI appliquée à la stack `docker-compose.yml` de ce dépôt (Ollama + Open WebUI + Postgres/pgvector + n8n), et explique **pourquoi** chaque réglage compte sur une machine sans GPU dédié.

- **Machine cible** : Ryzen 7 7840HS, iGPU Radeon 780M, 30 Go de RAM partagée
- **Modèles** : `granite4.2:8b` (chat, contexte 32k) et `bge-m3` (embeddings)
- **Versions testées** : Open WebUI 0.11.4, Ollama (image `latest`, backend Vulkan)

---

## 1. Comprendre les contraintes avant de régler quoi que ce soit

Trois faits matériels expliquent tous les choix qui suivent.

| Contrainte | Conséquence |
|---|---|
| L'iGPU n'adresse que ~15,8 Go de mémoire partagée (GTT) | Le modèle de chat doit faire ≤ ~8 Go. Sous Vulkan, impossible de répartir un gros modèle entre GPU et CPU. |
| La génération est limitée par la bande passante mémoire (DDR5) | Un modèle dense de 8B en Q4 (~5 Go) plafonne à **~14,5 tokens/s**. Aucun paramètre logiciel ne fait mieux. |
| Ollama tourne avec `OLLAMA_NUM_PARALLEL=1` | **Une seule requête à la fois.** Toute requête annexe (titre, tags…) passe *avant* ou *après* la vôtre et la fait attendre. |

Ordres de grandeur mesurés sur cette machine :

- lecture du prompt (*prompt eval*) : **~250 tokens/s** → 1 400 tokens de contexte RAG ≈ 5 s ;
- génération : **~14,5 tokens/s** → une réponse de 600 tokens ≈ 40 s ;
- indexation d'un document de 142 extraits avec `bge-m3` : ~38 s (batch de 1).

> **À retenir** : sur cette machine, chaque token généré coûte ~70 ms. L'essentiel de l'optimisation consiste à **ne pas faire générer de tokens inutiles** au modèle.

### Le symptôme de départ

Une requête avec un document joint ne répondait toujours pas après 5 minutes. Les logs Ollama (`docker compose logs -f ollama`) ont montré deux causes cumulées :

1. **Des tâches d'arrière-plan en file d'attente** : quatre appels d'environ 1 min 50 chacun (titre, tags, suggestions, requêtes de recherche) ont précédé la réponse. Celle-ci n'a démarré qu'au bout de 2 minutes.
2. **Un raisonnement emballé** : `granite4.2:8b` raisonne par défaut (*thinking*). Il avait produit plus de 2 500 tokens de réflexion sans un seul mot de réponse.

Après les réglages ci-dessous, la même requête aboutit en **25 à 45 s**.

---

## 2. Premier démarrage

1. Lancer la stack : `cp .env.example .env` (éditer les secrets), puis `docker compose up -d`.
2. Ouvrir http://localhost:3000 et créer le compte. **Le premier compte créé devient administrateur.**
3. Vérifier que le modèle est chargé à 100 % sur le GPU :

   ```bash
   docker compose exec ollama ollama ps
   # PROCESSOR doit afficher "100% GPU"
   ```

> ⚠️ **PersistentConfig** : au premier démarrage, Open WebUI copie les variables d'environnement (`RAG_TOP_K`, `CHUNK_SIZE`…) dans sa base (`webui.db`). Ensuite, **c'est la base qui fait foi**. Modifier `docker-compose.yml` n'a plus d'effet sur ces réglages : il faut passer par l'interface d'administration.

---

## 3. Réglages du modèle

**Chemin** : *Admin Panel → Settings → Models → granite4.2:8b*

Ces réglages s'appliquent à toutes les conversations qui utilisent ce modèle. Ils sont enregistrés dans la base d'Open WebUI et non dans Ollama.

### 3.1 Advanced Params

Cliquer sur **Show** à droite de *Advanced Params* pour afficher la liste. Chaque paramètre affiche *Default* tant qu'on ne clique pas dessus.

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

**Builtin Tools** : ❌ **décoché**.

En mode *Function Calling: Native*, chaque outil intégré activé (mémoire, notes, calendrier, base de connaissances…) est **décrit dans le prompt de chaque requête**. Cela a trois conséquences :

- **le prompt s'allonge** et chaque message coûte plusieurs secondes de lecture supplémentaires ;
- **un modèle de 8B se disperse** face à une quinzaine d'outils et en appelle d'inutiles, ce qui ajoute à chaque fois un aller-retour complet ;
- **avec les outils *Files* et *Knowledge Base* actifs**, Open WebUI peut laisser au modèle le soin d'aller lire le document par un appel d'outil au lieu d'injecter directement les extraits. Un petit modèle oublie souvent de le faire et répond sans avoir lu le document.

Builtin Tools désactivé, les fichiers joints à la conversation et les bases appelées par `#` passent par le RAG classique : Open WebUI recherche lui-même les extraits pertinents et les place dans le prompt.

> ⚠️ Ce n'est **pas** le cas d'une base **rattachée à un assistant** du Workspace. En mode Native, celle-ci n'est consultable que par l'outil intégré `query_knowledge_files`. Un assistant documentaire doit donc passer en *Function Calling: Legacy*. Voir [Créer un assistant dans le Workspace, §5.4](assistant-workspace-open-webui.md#54-le-choix-décisif--legacy-ou-native).

### 3.3 System Prompt

> **Où le mettre** : laissez le System Prompt du **modèle de base vide**. Une consigne comme « answer only from the provided context » s'appliquerait à toutes les conversations, et le modèle refuserait les questions générales. Placez-la dans un **assistant** du Workspace (*Workspace → Models*), comme décrit dans [Créer un assistant dans le Workspace](assistant-workspace-open-webui.md). Le texte et son explication ci-dessous restent valables.

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

Adapter le rôle (« MBSE expert ») au domaine des documents. La consigne est en anglais parce que les documents le sont, mais le modèle répond quand même dans la langue de la question.

Valider avec **Save & Update**.

---

## 4. Tâches d'arrière-plan

**Chemin** : *Admin Panel → Settings → **Admin › Experience › Interface*** → section **Tasks**

> Attention à ne pas confondre avec *Personal › Interface* (en haut du menu), qui ne contient que les préférences d'affichage de l'utilisateur.

Open WebUI utilise le modèle de chat pour de petites tâches automatiques. Avec une seule requête traitée à la fois, **chacune bloque le GPU** : avant la réponse, elle retarde son démarrage ; après, elle retarde la question suivante.

| Tâche | Valeur | Coût mesuré | Ce que ça implique |
|---|---|---|---|
| **Follow Up Generation** | **Off** | ~14 s après chaque réponse | Propose des questions de relance cliquables. Agréable, mais c'est la tâche la plus coûteuse : ~150 tokens générés à chaque réponse. |
| **Tags Generation** | **Off** | ~5 s | Classe automatiquement les conversations par mots-clés. Peu utile pour un usage individuel. |
| **Title Generation** | Off *(ou On)* | ~5 s | Donne un titre à la conversation au premier échange. Coût faible (~20 tokens) : c'est une question de confort. Désactivé, le titre reprend le début du premier message. |
| **Retrieval Query Generation** | **On** | ~5–7 s avant la réponse | Avant de chercher dans les documents, le modèle reformule la question en requêtes de recherche. C'est utile en conversation : « et pour le niveau L3 ? » devient une requête autonome sur le bon sujet. À désactiver si on pose toujours des questions complètes et qu'on veut gagner quelques secondes. |
| **Web Search Query Generation** | **Off** | — | Sert uniquement à la recherche web, qui n'est pas configurée. |
| **Autocomplete Generation** | **Off** | à chaque frappe | Propose des complétions pendant la saisie. Rédhibitoire sur un iGPU : chaque pause dans la frappe lance une génération. |

**Task Model** : on peut y désigner un modèle plus petit et plus rapide dédié à ces tâches. Ici on garde *Current Model*, car charger un second modèle de chat réduirait la mémoire GPU disponible.

Valider avec **Save**.

---

## 5. Documents et RAG

**Chemin** : *Admin Panel → Settings → Tools › Documents*

| Paramètre | Valeur | Ce que ça implique |
|---|---|---|
| **Embedding Model Engine / Model** | Ollama / `bge-m3` | Modèle multilingue (FR/EN) qui transforme chaque extrait en vecteur. Il tourne sur le GPU via Ollama et reste chargé à côté du modèle de chat (`OLLAMA_MAX_LOADED_MODELS=2`). |
| **Embedding Batch Size** | **32** | Nombre d'extraits envoyés en une fois au modèle d'embedding. À 1 (valeur par défaut), un document de 142 extraits fait 142 appels successifs (~38 s). En lot, l'indexation est plusieurs fois plus rapide. Cela n'a aucun effet sur la qualité. |
| **Vector Database** | pgvector (`rag`) | Les vecteurs sont stockés dans Postgres (table `document_chunk`) et partagés avec n8n. |
| **Chunk Size / Overlap** | 1000 / 150 | Taille des extraits en caractères (~250 tokens) et chevauchement entre deux extraits consécutifs. Des extraits plus petits rendent la recherche plus précise mais donnent moins de contexte. Le chevauchement évite de couper une idée en deux. |
| **Markdown Header Text Splitter** | On | Découpe d'abord le document selon ses titres, puis selon la taille. Les extraits respectent ainsi la structure (sections, sous-sections). |
| **Hybrid Search** | On | Combine la recherche par mots-clés (BM25) et la recherche sémantique (vecteurs). Le BM25 retrouve les termes exacts (acronymes, références comme « SysML v2 » ou « §4.2 »), là où la recherche sémantique seule échoue souvent sur du contenu technique. |
| **Top K** | **8** | Nombre d'extraits injectés dans le prompt. À 5 (valeur par défaut, ~1 250 tokens), une question sur les livrables d'un cahier des charges a oublié le principal : le tableau des livrables était coupé en deux extraits, et un des 5 extraits était occupé par la table des matières. À 8 (~2 000 tokens), il faut compter ~4 s de lecture en plus par question, contre une bien meilleure couverture des listes et des tableaux. Au-delà de 10, le gain diminue et un modèle de 8B se perd dans trop de contexte. |
| **Relevance Threshold** | 0 | Aucun filtrage par score : les 5 meilleurs extraits sont toujours transmis. |

### Limite du RAG : questions ciblées ou résumé global

Le RAG ne transmet au modèle que les **5 extraits les plus pertinents**, par exemple 5 sur les 142 d'un rapport.

- ✅ **Questions ciblées** (« que recommande le rapport pour les profils L2 et L3 ? ») : c'est le cas d'usage idéal.
- ⚠️ **Résumé global** (« résume ce document ») : le modèle ne voit qu'environ 4 % du texte et le résumé sera partiel.

Pour un résumé, cliquer sur le fichier joint et choisir l'option qui utilise **le document entier** (*full context*). Le contenu complet est alors injecté, à deux conditions :

- **le document doit tenir dans le contexte de 32k tokens**, soit ~100 pages de texte dense ;
- **il faut accepter la lecture du prompt** : ~2 minutes pour 30 000 tokens à ~250 tokens/s.

Pour les gros documents, préférer un résumé section par section, ou un workflow n8n de résumé progressif.

---

## 6. Créer une base de connaissances

Joindre un fichier à une conversation l'indexe **pour cette conversation seulement**. Pour un corpus qu'on interroge régulièrement, on crée une base de connaissances : les documents y sont indexés une seule fois, et on peut l'interroger depuis n'importe quelle conversation.

### 6.1 Création

1. **Workspace** → onglet **Knowledge** → bouton **Create** en haut à droite.

   > Le bouton *Create* crée l'élément de l'onglet affiché. Sur l'onglet *Models*, il crée un modèle, pas une base.

2. Renseigner un **nom** et une **description**. La description est visible par le modèle et l'aide à savoir quand s'en servir : décrire le contenu (« Rapports et cahiers des charges sur l'impact de SysML v2… ») plutôt que l'usage.
3. Ajouter les documents par glisser-déposer et attendre la fin de l'indexation de chacun. Avec un batch de 32, un document de 170 extraits est indexé en ~13 s.

### 6.2 Choisir le bon format de fichier

Tous les formats ne se valent pas. La qualité des réponses dépend d'abord de la qualité de l'extraction du texte.

| Format | Qualité | Pourquoi |
|---|---|---|
| **DOCX, Markdown** | ✅ Bonne | Les titres sont reconnus : le découpage suit les sections. Les tableaux gardent leurs lignes et leurs colonnes. |
| **PDF** | ⚠️ Moyenne | Le texte est extrait page par page, sans structure. **Les tableaux sont aplatis** et leurs colonnes se mélangent. La **table des matières** et les **pieds de page** (mentions de copyright…) deviennent des extraits à part entière, qui encombrent la recherche. |
| PDF scanné | ❌ | Aucun texte sans OCR (non configuré dans cette stack). |

Exemple observé : dans un tableau comparatif extrait d'un PDF, le modèle a attribué à Acme Défense une classification qui appartenait à une autre organisation, parce que les colonnes étaient mélangées.

> **Règle pratique** : quand un document existe en DOCX et en PDF, indexer le DOCX.

### 6.3 Interroger la base

- **Ponctuellement** : dans une conversation, taper `#` puis choisir la base.
- **En permanence** : créer un assistant (par exemple « Expert MBSE ») dans *Workspace → Models*, avec la base rattachée, un prompt système dédié et *Function Calling* en **Legacy**. Voir [Créer un assistant dans le Workspace](assistant-workspace-open-webui.md).

### 6.4 Contrôler l'indexation

Les extraits sont stockés dans la table `document_chunk` de la base `rag`. La colonne `collection_name` contient l'identifiant de la base de connaissances, ou `file-<id>` pour un fichier joint à une conversation.

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d rag -c "
  SELECT collection_name, vmetadata->>'name' AS fichier, count(*) AS extraits
  FROM document_chunk GROUP BY 1, 2 ORDER BY 1;"
```

Pour vérifier qu'un passage précis a été correctement extrait :

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d rag -c "
  SELECT vmetadata->>'page', left(text, 300) FROM document_chunk
  WHERE text ILIKE '%deliverable%' LIMIT 5;"
```

À noter : les fichiers joints aux conversations restent indexés dans leur propre collection même après la fin de la conversation.

---

## 7. Tester le RAG

Une réponse qui « a l'air bonne » ne suffit pas : il faut vérifier qu'elle est **complète** et **fidèle**. Pour cela, poser une série de questions qui testent chacune un aspect différent, et **cliquer sur les citations** sous chaque réponse pour lire les extraits transmis au modèle.

| # | Type de question | Exemple | Ce qu'on vérifie |
|---|---|---|---|
| 1 | Un fait précis, dans un seul document | « Quels livrables sont demandés dans le SOW ? » | La recherche trouve le bon passage, et la liste est complète. |
| 2 | Un terme exact (acronyme, nom propre, section) | « Que dit la section 4.3 ? » | La recherche par mots-clés (BM25) fonctionne. |
| 3 | Une question qui demande plusieurs documents | « La proposition couvre-t-elle tous les livrables du SOW ? » | La recherche rapporte des extraits de plusieurs sources. |
| 4 | Une relance | après la 3 : « et quels sont les risques ? » | La reformulation de la question (*Retrieval Query Generation*). |
| 5 | **Une information absente des documents** | « Quel est le coût de licence par poste ? » | Le modèle dit qu'il ne sait pas. **C'est le test le plus important.** |

### Diagnostiquer une mauvaise réponse

Toujours comparer la réponse aux citations. L'origine du problème est souvent dans la recherche, pas dans le modèle.

| Constat | Cause | Remède |
|---|---|---|
| Un élément manque, et il n'apparaît dans **aucune** citation | La recherche ne l'a pas trouvé (extrait coupé, Top K trop faible). | Augmenter Top K, reformuler la question avec les termes exacts du document. |
| L'élément est **dans** une citation mais pas dans la réponse | Le modèle a résumé au lieu d'énumérer. | Renforcer le prompt système (« list all of them »). |
| Une citation pointe vers une table des matières ou un pied de page | Bruit d'extraction du PDF. | Indexer le DOCX à la place. |
| Une information est attribuée au mauvais acteur | Tableau aplati par l'extraction PDF. | Indexer le DOCX, ou interroger la section concernée directement. |
| Une réponse précise sur un sujet absent des documents | Hallucination. | Vérifier le prompt système (« answer only from the provided context »). |

---

## 8. Vérifier que tout fonctionne

Suivre les logs pendant une requête :

```bash
docker compose logs -f ollama | grep -E 'POST|new prompt|prompt eval|eval time'
```

Ce qu'on doit observer pour une question avec un document joint :

```text
POST "/api/chat" | 3.8s                        ← reformulation de la question (Retrieval Query Generation)
new prompt, ... task.n_tokens = 1891           ← prompt système + question + extraits du document
prompt eval time = 7181 ms / 1801 tokens       ← ~250 tokens/s
       eval time = 15626 ms / 226 tokens       ← ~14,5 tokens/s
POST "/api/chat" | 22.8s
```

Signes d'un problème :

| Observation | Cause probable |
|---|---|
| `task.n_tokens` de quelques centaines avec un document joint | Les extraits ne sont pas injectés : vérifier *Builtin Tools* (3.2) et, pour un assistant, le mode *Function Calling* (Legacy). |
| Plusieurs `POST /api/chat` avant que la réponse ne s'affiche | Des tâches d'arrière-plan sont encore actives (section 4). |
| Génération longue avec une réponse vide à l'écran | *think* n'est pas désactivé (3.1). |
| `ollama ps` affiche un pourcentage de CPU | Le modèle ne tient pas en mémoire GPU : réduire le contexte ou changer de modèle. |

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
| | Top K | 8 |
| Workspace › Knowledge | documents | DOCX de préférence au PDF |

**Résultat** : une question sur un document passe de plus de 5 minutes (sans aboutir) à **25–45 secondes** selon la longueur de la réponse, et le GPU est libre dès la fin de la réponse.

### Pour aller plus loin

- **Gagner en vitesse de génération** : seul un modèle *Mixture of Experts* (par exemple `granite4:tiny-h`, ~1B paramètres actifs par token) peut dépasser le plafond de ~14,5 tokens/s, au prix d'un raisonnement moins solide.
- **Améliorer le classement des extraits** : un modèle de *reranking* (par exemple `bge-reranker-v2-m3`) reclasse les extraits trouvés avant de les envoyer au modèle. La pertinence s'améliore, mais le calcul se fait sur le CPU du conteneur Open WebUI et ajoute quelques secondes par question.
- **Nettoyer pgvector** : supprimer les collections `file-*` des fichiers joints lors d'essais (voir 6.4).
