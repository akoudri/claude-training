# Détection des termes sensibles par LLM local — conception

Date : 2026-10-08

## Objectif

L'obfuscation par dictionnaires ne masque que les termes listés : un nom oublié passe en clair. La commande
`detecter` lit les documents bruts **en local**, demande à un LLM servi par Ollama d'y repérer les entités nommées,
et produit un **dictionnaire candidat** que l'utilisateur relit avant de lancer `obfusquer`. Rien ne quitte la
machine : c'est l'étape qui précède l'envoi à Claude, elle ne doit donc jamais faire appel à Claude.

La détection est une aide à la constitution du dictionnaire, pas une garantie : le dictionnaire validé par
l'utilisateur reste la seule référence, et la relecture des documents obfusqués reste nécessaire.

## Décisions

| Sujet | Décision |
|---|---|
| Emplacement | Troisième commande du paquet `obfuscation`, à côté d'`obfusquer` et `restaurer`. Pas de workflow n8n. |
| Moteur | LLM local via l'API Ollama `/api/chat`, sortie structurée (schéma JSON dans `format`), température 0. Pas de spaCy. |
| Serveur Ollama | Quelconque, désigné par une URL (`--ollama-url`, défaut `http://127.0.0.1:11434`) : l'Ollama de la stack `local-llm` (conteneur publié sur la boucle locale) ou un Ollama natif (recommandé sous macOS, où Docker n'a pas accès au GPU). Jamais la passerelle `ollama-gateway`, limitée à `/v1/messages`. |
| Catégories | Jeu par défaut `CLIENT, PRESTATAIRE, PROJET, PERSONNE, LIEU`, remplaçable par `--categories`. |
| Sortie | Un YAML au format des dictionnaires, commenté, directement utilisable par `obfusquer -d`. Pas de validation interactive. |
| Motifs | Non détectés : le LLM ne propose que des termes ; les regex restent écrites à la main. |
| Dépendances | Aucune nouvelle : client HTTP en `urllib` de la bibliothèque standard. |

## Utilisation

```bash
cd local-llm && docker compose up -d ollama        # ou un Ollama natif
cd obfuscation
uv run detecter documents/ -o client.candidats.yaml [-d dictionnaires/client.yaml] \
    [--modele granite4.2:8b] [--ollama-url http://127.0.0.1:11434] \
    [--categories CLIENT,PRESTATAIRE,PROJET,PERSONNE,LIEU] [--delai 300]
# relire client.candidats.yaml, supprimer les lignes refusées, puis :
uv run obfusquer documents/ -d dictionnaires/client.yaml -d client.candidats.yaml -t client.table.json -o sortie/
```

- Entrées : fichiers et dossiers, parcours récursif, mêmes extensions qu'`obfusquer`
  (`.docx`, `.xlsx`, `.pptx`, `.pdf`, `.md`, `.txt`) ; les autres fichiers sont ignorés et signalés.
- `-d` (répétable) : dictionnaires existants ; leurs termes et variantes sont exclus des propositions.
- `-o` : fichier YAML à créer. **Refus s'il existe déjà** : un candidat relu et corrigé ne doit pas être écrasé.
- Modèle par défaut : `granite4.2:8b`, celui de la stack `local-llm`.

## Architecture

```
src/obfuscation/
  extraction.py          # texte brut d'un fichier, via les adaptateurs de formats existants
  detection/
    __init__.py
    decoupage.py         # morceaux de texte pour le modèle
    ollama.py            # client /api/chat
    candidats.py         # post-traitement déterministe
    sortie.py            # écriture du YAML commenté
  cli.py                 # + main_detecter ; pyproject : detecter = "obfuscation.cli:main_detecter"
```

Parcours :

```
fichiers → extraction (texte par fichier) → découpage → Ollama ({terme, categorie}[] par morceau)
        → candidats (présence vérifiée, filtrage, fusion, exclusion) → YAML commenté
```

### Extraction

Pas de nouveau parseur. Les adaptateurs de `formats/` n'utilisent du moteur que `transformer()`,
`remplacements()`, `avertissements` et `table`. Un `Collecteur` offre ces membres : il enregistre chaque texte reçu
et ne remplace rien (`transformer` renvoie le texte tel quel, `remplacements` une liste vide). Word, Excel,
PowerPoint et PDF sont ainsi lus exactement comme `obfusquer` les lit (notes de bas de page, commentaires, en-têtes,
cellules, noms de feuilles compris). La répartition par extension (dont la conversion PDF → Markdown) est celle de
`cli._transformer` ; elle est déplacée dans un module partagé si nécessaire, sans changement de comportement. Les
données produites par l'adaptateur sont ignorées ; aucun fichier n'est écrit.

Les noms de fichiers font aussi partie du texte collecté : `Proposition Novaltis.docx` doit révéler `Novaltis`.

### Découpage

- Morceaux d'environ 2 000 tokens, estimés à 4 caractères par token (8 000 caractères) : un modèle de 8 milliards
  de paramètres est plus fiable sur un texte court.
- Coupe aux fins de paragraphe ; chevauchement d'un paragraphe entre deux morceaux, pour qu'une entité à cheval ne
  soit pas perdue.
- Un paragraphe plus long qu'un morceau est coupé en fin de phrase, à défaut sur une espace.

### Client Ollama

- `POST {url}/api/chat`, `stream: false`, `options.temperature: 0`, `format` = schéma JSON :
  `{"entites": [{"terme": string, "categorie": enum(catégories demandées)}]}`.
- Message système : rôle, catégories avec une définition d'une ligne chacune, consignes (recopier le terme
  exactement comme écrit ; noms propres uniquement, pas « le client » ni « la société » ; une entrée par forme
  rencontrée), un court exemple inventé, étranger au corpus Héron pour ne pas fausser la mesure.
- Message utilisateur : le morceau de texte.
- Délai par appel : `--delai`, 300 s par défaut (mode CPU lent).

### Post-traitement (`candidats.py`)

Déterministe, testable sans modèle. Pour chaque proposition :

1. **Présence vérifiée** : le terme doit apparaître dans le morceau, selon les règles de correspondance de
   `dictionnaire.py` (`normaliser`, limites de mot par lettres). Sinon il est rejeté et compté. La forme retenue est
   celle **du texte**, pas celle renvoyée par le modèle.
2. **Filtrage** : moins de 3 caractères, terme sans lettre (les nombres relèvent des motifs), ou mot générique d'une
   courte liste (client, société, projet, direction, équipe…) → écarté.
3. **Exclusion** : terme déjà couvert par un dictionnaire `-d` (comparaison par `normaliser`) → écarté.

Puis sur l'ensemble des documents :

4. **Fusion des variantes**, au sein d'une même catégorie :
   - même forme une fois accents et casse retirés (`Acme Défense` / `Acme Defense`) → une entrée ;
   - terme contenu, par mots entiers, dans un terme plus long (`Acme` dans `Acme Défense`) → variante du plus long,
     marquée « variante présumée, à vérifier ».
   - Première variante : la forme complète la plus fréquente (celle que `restaurer` remet en place).
5. **Conflit de catégorie** (même terme, catégories différentes selon les morceaux) : la plus fréquente l'emporte ;
   le commentaire cite l'autre.

### Sortie YAML

```yaml
# Dictionnaire candidat produit par « detecter » le 2026-10-08 (modèle granite4.2:8b).
# À relire : supprimer les lignes refusées, corriger les catégories. Rien n'est appliqué sans « obfusquer ».
# Morceaux non analysés : aucun.
CLIENT:
  - [Acme Défense, Acme Defense, Acme]  # 14 occurrences ; « Acme » : variante présumée, à vérifier
                                        # « …le marché passé par Acme Défense pour… »
PERSONNE:
  - Jeanne Martin                       # 3 occurrences — « …signé par Jeanne Martin, responsable… »
```

- Catégories dans l'ordre demandé, termes par nombre d'occurrences décroissant.
- Un extrait de contexte (une quarantaine de caractères de part et d'autre) par entrée.
- Le fichier est relu par `Dictionnaire` avant d'être écrit : il doit être chargeable tel quel par `obfusquer`.
- Le fichier contient des termes réels : `*.candidats.yaml` est ajouté au `.gitignore`.

## Gestion des erreurs

Codes de retour alignés sur `obfusquer` : `0` succès, `1` résultat incomplet, `2` erreur de configuration.

| Cas | Effet | Code |
|---|---|---|
| Ollama injoignable | Arrêt avant tout traitement, suggestion `docker compose up -d ollama` (depuis `local-llm/`) | 2 |
| Modèle absent (404) | Arrêt, suggestion `ollama pull <modele>` | 2 |
| `-o` existe déjà, catégorie invalide, dictionnaire `-d` illisible | Arrêt | 2 |
| Fichier illisible (corrompu, PDF scanné) | Fichier ignoré, message, poursuite | 1 |
| JSON invalide ou délai dépassé sur un morceau | Un nouvel essai, puis morceau ignoré avec avertissement ; le YAML est écrit et son en-tête liste les morceaux non analysés | 1 |

Progression sur la sortie d'erreur : `fichier.docx — morceau 3/12`. Bilan final : nombre de candidats, de
propositions rejetées (absentes du texte), de morceaux ignorés.

## Tests

Suite pytest, sans modèle ni réseau externe :

- **Découpage** : taille, chevauchement, coupe aux paragraphes, paragraphe plus long qu'un morceau.
- **Candidats** : terme inventé rejeté, forme du texte conservée, accents / casse / apostrophes et tirets
  typographiques, fusion des variantes, variante présumée, conflit de catégorie, filtrage, exclusion des termes `-d`.
- **Client Ollama** : faux serveur `http.server` dans un thread ; requête envoyée (modèle, schéma, température),
  connexion refusée, 404, JSON invalide puis nouvel essai, délai dépassé.
- **Extraction** : le `Collecteur` restitue le texte des documents de `tests/documents.py` (notes de bas de page,
  cellules, diapositives, PDF) et ne modifie aucun fichier.
- **CLI** : parcours complet avec un client Ollama simulé ; YAML chargeable par `Dictionnaire` ; refus d'écraser
  `-o` ; codes de retour.

## Mesure

Hors de la suite pytest, avec Ollama démarré.

- `exemples/mesurer.py` lance la détection sur les documents produits par `exemples/generer.py` (corpus Héron) et
  les compare à `exemples/dictionnaire.yaml` : **rappel** (termes de référence retrouvés, l'indicateur décisif : un
  oubli est une fuite), **précision** (propositions justes), durée par document attribuée à la configuration de
  référence. Trois exécutions, pour mesurer la variabilité.
- Le corpus Héron ne compte que 5 entités et aucun lieu : la mesure est indicative, pas probante.
- Sur des documents réels, l'utilisateur lance lui-même le script, avec son propre dictionnaire validé comme
  référence. **Le script n'affiche que des chiffres, jamais les termes** : sa sortie peut ainsi être partagée, y
  compris avec Claude, sans fuite.

## Intégration dans le dépôt

- `pyproject.toml` : point d'entrée `detecter`.
- `.gitignore` : `*.candidats.yaml`.
- `README.md` d'`obfuscation/` : section « Détecter les termes avec un LLM local », limites (la détection peut
  oublier des termes ; relire le candidat puis les documents obfusqués).
- `CLAUDE.md` racine : mention de la commande dans la description d'`obfuscation/`.

## Hors périmètre

- spaCy ou toute autre NER classique (à reconsidérer si le rappel mesuré est insuffisant).
- Détection des motifs (regex).
- Cache des réponses, appels parallèles (la stack impose `OLLAMA_NUM_PARALLEL=1`).
- Validation interactive des candidats.
- Enrichissement du corpus d'exemples.
