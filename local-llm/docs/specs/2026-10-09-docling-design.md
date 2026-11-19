# Conversion des PDF par Docling pour Open WebUI — conception

Date : 2026-10-09

## Objectif

Avec son extracteur intégré, Open WebUI lit un PDF page par page, sans structure : les tableaux sont aplatis et leurs
colonnes se mélangent, la table des matières et les pieds de page deviennent des extraits à part entière. Le
tutoriel 01 (section 6.2) le constate et contourne le problème (« indexer le DOCX »), mais un PDF déposé dans une
base ou une conversation donne toujours des réponses de mauvaise qualité : informations attribuées au mauvais
acteur, citations qui pointent vers un pied de page.

Le service optionnel **Docling** (`docling-serve`) convertit les documents en Markdown en analysant la mise en page :
tableaux restitués en tableaux Markdown, en-têtes et pieds de page reconnus et écartés, titres conservés (le
découpage suit alors les sections). Open WebUI sait l'appeler nativement (`CONTENT_EXTRACTION_ENGINE=docling`).

Le problème constaté est la qualité des réponses, pas les PDF scannés : l'OCR reste désactivé par défaut.

## Décisions

| Sujet | Décision |
|---|---|
| Périmètre | Open WebUI seulement (bases de connaissances et fichiers joints aux conversations). L'ingestion n8n (`01-ingestion`) garde son chargeur ; elle fera l'objet d'un travail séparé si besoin. |
| Moteur | `docling-serve`, image CPU `quay.io/docling-project/docling-serve-cpu`, version explicite (comme n8n). Pas de service maison (pymupdf4llm : tableaux moins fiables, code à maintenir, licence AGPL) ni de conversion manuelle avant dépôt. |
| Activation | **Overlay optionnel** `docker-compose.docling.yml`, ajouté à `COMPOSE_FILE` comme `docker-compose.n8n.yml`. Sans lui, Open WebUI garde son extracteur intégré et la stack démarre aussi vite qu'aujourd'hui. |
| Formats concernés | Tous les fichiers non texte passent par Docling (PDF, DOCX, PPTX, XLSX…) ; Markdown et texte brut restent lus directement par Open WebUI (comportement d'Open WebUI 0.11, `retrieval/loaders/main.py`). |
| OCR | Désactivé (`do_ocr=false`) : il ne sert qu'aux PDF scannés et multiplie le temps de conversion. Le tutoriel explique comment le réactiver. |
| Mode des tableaux | `table_mode` `fast` ou `accurate`, choisi d'après la mesure sur la configuration de référence (qualité sur le PDF d'exemple, temps par page). |
| Synchronisation de la configuration | `open-webui-init` aligne la configuration d'Open WebUI sur la présence de l'overlay, dans les deux sens, par l'API d'administration (voir plus bas). |
| PDF d'exemple | PDF fictif, généré par un script versionné, rangé avec son script dans `open-webui/exemples/`. Il n'est pas ajouté à la base `MBSE Expert`. |

## Overlay `docker-compose.docling.yml`

En-tête de commentaires sur le modèle de `docker-compose.n8n.yml` : rôle du service, activation par `COMPOSE_FILE`,
séparateur `;` sous Windows hors WSL.

**Service `docling`**

- image `quay.io/docling-project/docling-serve-cpu:<version>`, version récente vérifiée au moment de
  l'implémentation ;
- `restart: unless-stopped` ;
- réseau interne de la stack uniquement, aucun port publié sur l'hôte ;
- `DOCLING_SERVE_MAX_SYNC_WAIT` relevé bien au-delà des 120 s par défaut : Open WebUI appelle le point d'entrée
  synchrone `/v1/convert/file`, et une conversion plus longue que ce délai échoue en HTTP 504. Valeur fixée d'après la
  mesure (ordre de grandeur visé : un document de quelques centaines de pages) ;
- `mem_limit` réglable par `.env` (`DOCLING_MEM_LIMIT`, valeur par défaut d'après la mesure) ;
- `healthcheck` sur le point de santé de `docling-serve`, avec un `start_period` qui couvre le chargement des
  modèles de mise en page.

**Ajouts au service `open-webui`**

- `CONTENT_EXTRACTION_ENGINE=docling` ;
- `DOCLING_SERVER_URL=http://docling:5001` ;
- `DOCLING_PARAMS` (JSON) : `do_ocr` à `false`, `do_table_structure` à `true`, `table_mode` retenu ;
- `depends_on` : `docling` en état `service_healthy`.

Ces variables relèvent de la PersistentConfig : elles ne s'appliquent qu'au premier démarrage d'un volume neuf
(par exemple sans `WEBUI_ADMIN_EMAIL`, quand `open-webui-init` ne fait rien).

**Ajouts au service `open-webui-init`**

- `OPENWEBUI_DOCLING=true` ;
- `depends_on` : `docling` en état `service_healthy`.

`docker-compose.yml` n'a pas besoin de déclarer `OPENWEBUI_DOCLING` : l'absence de la variable vaut « overlay non
chargé ».

## Synchronisation par `open-webui-init`

Problème : une installation existante a déjà son moteur d'extraction enregistré dans `webui.db` ; ajouter l'overlay
n'y change rien. À l'inverse, retirer l'overlay laisserait Open WebUI configuré sur un serveur Docling disparu : tout
dépôt de fichier non texte échouerait.

`configurer.py` gagne une étape, exécutée après la connexion et avant le réglage du modèle de base :

1. lire la configuration : `GET /api/v1/retrieval/config` ;
2. décider, par une fonction pure `reglage_extraction(config, docling_actif)` qui renvoie les champs à envoyer, ou
   `None` s'il n'y a rien à changer :

   | Overlay (`OPENWEBUI_DOCLING`) | Moteur actuel | Action |
   |---|---|---|
   | chargé | quelconque | moteur `docling`, `DOCLING_SERVER_URL`, `DOCLING_PARAMS` de l'overlay (rien à envoyer si déjà identiques) |
   | absent | `docling` | moteur `""` (extracteur intégré) |
   | absent | autre (`""`, `tika`…) | rien : un choix fait à la main dans l'interface est respecté |

3. si nécessaire, envoyer les champs par `POST /api/v1/retrieval/config/update` (mise à jour partielle : les champs
   absents gardent leur valeur) ;
4. afficher une ligne d'état, sur le modèle des autres étapes : `extraction des documents : Docling (réglé)`,
   `… : Docling (inchangé)`, `… : extracteur intégré (Docling retiré)`, `… : <moteur> (inchangé)`.

Les valeurs (URL, paramètres) sont transmises à `open-webui-init` par l'overlay
(`DOCLING_SERVER_URL`, `DOCLING_PARAMS`), pour qu'elles ne soient écrites qu'à un seul endroit.

Comportement inchangé sans `WEBUI_ADMIN_EMAIL` / `WEBUI_ADMIN_PASSWORD` : rien n'est configuré.

Avertissement à documenter : relancer `open-webui-init` remet le moteur d'extraction aux valeurs de l'overlay, comme
il remet déjà le modèle de base aux valeurs de la section 3.

## Gestion des erreurs

| Situation | Comportement |
|---|---|
| Docling pas encore prêt | `open-webui` et `open-webui-init` attendent son `healthcheck`. |
| Conversion plus longue que `DOCLING_SERVE_MAX_SYNC_WAIT` | Open WebUI affiche l'échec de l'indexation ; le tutoriel indique le remède (relever la valeur, ou découper le document). |
| Docling arrêté alors que l'overlay est chargé | Échec de l'indexation dans Open WebUI ; ligne de dépannage dans le tutoriel (`docker compose ps docling`, logs). |
| Mémoire insuffisante (conteneur tué) | Ligne de dépannage : relever `DOCLING_MEM_LIMIT`. |
| API d'Open WebUI en erreur pendant la synchronisation | `Echec` comme les autres étapes : message sur la sortie d'erreur, code de sortie 1. |

## PDF d'exemple

`open-webui/exemples/generer-pdf.py` produit `open-webui/exemples/matrice-acteurs-heron.pdf`, versionné avec lui
(document fictif, cohérent avec le corpus Projet Héron). Le script s'exécute sans installation durable :
`uv run --with reportlab==<version> open-webui/exemples/generer-pdf.py`.

Contenu, conçu pour reproduire les défauts de l'extracteur intégré :

- une table des matières en première page ;
- un tableau sur plusieurs colonnes qui associe chaque organisation (Acme Défense, Novaltis, et une ou deux autres)
  à un rôle, une classification et un statut, avec des valeurs proches d'une ligne à l'autre (c'est le cas où le
  modèle a attribué à Acme Défense la classification d'une autre organisation) ;
- un pied de page répété sur chaque page (mention de diffusion et numéro de page) ;
- deux à trois pages.

Les questions de test et leurs réponses attendues figurent dans le tutoriel 01.

## Documentation (en français)

- **`.env.example`** : expliquer qu'on ajoute `:docker-compose.docling.yml` à la fin de n'importe quelle ligne
  `COMPOSE_FILE`, plutôt que de lister toutes les combinaisons ; ajouter `DOCLING_MEM_LIMIT`.
- **Tutoriel 01**
  - section 2 : mentionner l'overlay à côté de n8n (optionnel, peut être ajouté plus tard) ;
  - section 6.2 : nouvelle sous-section « Activer Docling » : ce qui change, coût mesuré sur la configuration de
    référence (taille de l'image, mémoire, secondes par page), activation, vérification
    (`docker compose logs open-webui-init`), réactivation de l'OCR pour les PDF scannés ; exercice avant/après avec le
    PDF d'exemple et ses réponses attendues ;
  - tableau des formats : ligne PDF selon que Docling est chargé ou non ; ligne PDF scanné (OCR possible avec
    Docling) ;
  - « Diagnostiquer une mauvaise réponse » : remède « activer Docling » pour les lignes table des matières / pied de
    page et tableau aplati ;
  - dépannage : délai dépassé (504), Docling injoignable, mémoire.
- **Tutoriel 02** : la règle « préférer DOCX ou Markdown au PDF » ne vaut que sans Docling.
- **Tutoriel 03** : préciser que l'ingestion n8n n'utilise pas Docling.
- **`local-llm/README.md`** : citer l'overlay dans la description de la stack.
- **`docker-compose.yml`** : citer l'overlay dans l'en-tête, à côté de n8n.

## Tests et vérification

- **Tests unitaires** de `reglage_extraction` (bibliothèque standard, `unittest`) dans
  `open-webui/test_configurer.py`, cinq cas : overlay chargé avec une configuration différente (réglage envoyé) ou
  identique (rien) ; overlay absent avec le moteur `docling` (retour à l'extracteur intégré), `""` (rien) ou `tika`
  (rien). Commande : `cd local-llm/open-webui && python3 -m unittest`.
- **Vérification sur la stack réelle** (celle du formateur, ou une copie jetable sous un autre nom de projet Compose
  comme lors du rejeu des tutoriels) :
  1. sans overlay : indexer le PDF d'exemple, poser les questions de test, noter réponses et citations ;
  2. avec overlay : `docker compose up -d`, vérifier la ligne d'`open-webui-init`, réindexer, reposer les questions,
     vérifier dans `document_chunk` que le tableau est en Markdown et que le pied de page a disparu ;
  3. retirer l'overlay : vérifier le retour à l'extracteur intégré et qu'un dépôt de PDF fonctionne ;
  4. mesurer : taille de l'image, mémoire au repos et en conversion, temps de conversion par page en `fast` et en
     `accurate` sur le PDF d'exemple et sur un PDF long. Ces chiffres fixent `table_mode`,
     `DOCLING_SERVE_MAX_SYNC_WAIT` et `DOCLING_MEM_LIMIT`, et sont cités dans le tutoriel comme mesures de la
     « configuration de référence ».

## Hors périmètre

- Ingestion n8n par Docling.
- OCR activé par défaut, profil GPU pour Docling.
- Ajout du PDF d'exemple à la base `MBSE Expert` créée par `open-webui-init`.
- Conversion asynchrone (`/v1/convert/file/async`) : Open WebUI 0.11 n'utilise que le point d'entrée synchrone.
