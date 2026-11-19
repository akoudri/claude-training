# Détection des termes sensibles par LLM local — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commande `detecter` qui lit des documents en local, demande à un LLM servi par Ollama d'y repérer les entités nommées et écrit un dictionnaire candidat commenté, directement utilisable par `obfusquer -d`.

**Architecture:** Le texte est extrait par les adaptateurs de formats existants, auxquels un `Collecteur` se présente avec l'interface du moteur. Il est découpé en morceaux, envoyé à `/api/chat` d'Ollama avec un schéma JSON, puis passé par un post-traitement déterministe (présence vérifiée, filtrage, exclusion, fusion des variantes, vote de catégorie) avant l'écriture du YAML. Un module de mesure compare le résultat à un dictionnaire de référence et n'affiche que des chiffres.

**Tech Stack:** Python 3.12, uv, bibliothèque standard (`urllib`, `http.server` pour les tests), PyYAML, code existant d'`obfuscation` ; tests : pytest.

**Spec:** `obfuscation/docs/specs/2026-10-08-detection-design.md`

## Global Constraints

- Toutes les commandes se lancent depuis `obfuscation/` (`cd obfuscation`). Tests : `uv run pytest`.
- Aucune nouvelle dépendance : client HTTP en `urllib`, faux serveur de test en `http.server`.
- Code, identifiants, messages et documentation en français.
- Codes de retour : `0` succès ; `1` résultat incomplet (fichier illisible, morceau non analysé) ; `2` erreur de configuration (Ollama injoignable, modèle absent, `-o` existant, catégorie invalide, dictionnaire `-d` illisible).
- Catégories par défaut : `CLIENT, PRESTATAIRE, PROJET, PERSONNE, LIEU`. Modèle par défaut : `granite4.2:8b`. URL par défaut : `http://127.0.0.1:11434`. Délai par appel : 300 s.
- Jamais d'appel à la passerelle `ollama-gateway` ; jamais d'appel à Claude.
- Le fichier `-o` n'est jamais écrasé. `*.candidats.yaml` ne doit jamais être versionné.
- Le script de mesure n'affiche ni terme ni nom de fichier.
- Identifiants fictifs uniquement dans les tests et les exemples (Novaltis, Acme Défense, Projet Héron, Jeanne Martin…). L'exemple du prompt est étranger au corpus Héron.
- Commits : Conventional Commits, messages en français, terminés par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Ne commiter qu'avec l'accord du formateur donné au lancement de l'exécution ; sans cet accord, laisser les changements dans l'arbre de travail et proposer le découpage à la fin. Ne jamais pousser.

## Écarts assumés par rapport à la spec

1. La comparaison avec la référence vit dans `src/obfuscation/detection/mesure.py`, testé par pytest. `exemples/mesurer.py` n'est qu'un script mince qui l'appelle.
2. La répartition par extension (`cli._transformer`) est déplacée dans `src/obfuscation/formats/fichier.py` (`transformer_fichier`), avec les ensembles d'extensions. Le comportement d'`obfusquer` et de `restaurer` est inchangé.
3. Un terme qui apparaît sous plusieurs casses (`Novaltis` / `NOVALTIS`) ne donne qu'une variante, la forme la plus fréquente : les dictionnaires sont insensibles à la casse.
4. Les messages de progression passent par `_signaler` avec le niveau `analyse` : `analyse : note.md — morceau 1/3`.

## Review Focus

1. **Le modèle écrit le terme autrement que le texte** (casse, apostrophe droite au lieu de typographique, espaces doublées, espace insécable) : le terme doit être accepté, et c'est la forme du texte qui est retenue. Test dans la tâche 5.
2. **Égalité de votes entre deux catégories** pour un même terme : le choix doit être déterministe (ordre des catégories demandées). Test dans la tâche 5.
3. **Termes contenant des caractères spéciaux pour YAML** (`R&D: Lyon`, `#Héron`, `'Atlas'`, `Dupont, Fils`, `[Projet] X`) : le YAML écrit doit rester chargeable par `obfusquer`. Test dans la tâche 6.
4. **Document sans texte** (présentation qui ne contient que des images, fichier vide) : aucun appel au modèle, aucune erreur. Test dans la tâche 7.
5. **Nom de modèle sans étiquette** (`granite4.2`, qu'Ollama liste comme `granite4.2:latest`) : doit être accepté, alors qu'un modèle non téléchargé est signalé avec `ollama pull`. Test dans la tâche 4.

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `src/obfuscation/formats/fichier.py` (créé) | Répartition par extension, `EXTENSIONS_TEXTE`, `EXTENSIONS_LISIBLES` |
| `src/obfuscation/extraction.py` (créé) | `Collecteur`, `extraire(source) -> str` |
| `src/obfuscation/detection/__init__.py` (créé) | Constantes par défaut, `Bilan`, `analyser()` |
| `src/obfuscation/detection/decoupage.py` (créé) | `decouper(texte, taille) -> list[str]` |
| `src/obfuscation/detection/prompt.py` (créé) | `message_systeme(categories)`, `schema(categories)` |
| `src/obfuscation/detection/ollama.py` (créé) | `ClientOllama`, `Proposition`, `ErreurOllama`, `ReponseInvalide` |
| `src/obfuscation/detection/candidats.py` (créé) | `Candidat`, `Collecte` |
| `src/obfuscation/detection/sortie.py` (créé) | `rendre()`, `ecrire()` |
| `src/obfuscation/detection/mesure.py` (créé) | `Score`, `comparer()` |
| `src/obfuscation/cli.py` (modifié) | utilise `transformer_fichier` ; `main_detecter` |
| `pyproject.toml` (modifié) | point d'entrée `detecter` |
| `exemples/mesurer.py` (créé) | script de mesure |
| `tests/faux_ollama.py`, `tests/conftest.py` (créé / modifié) | faux serveur Ollama et sa fixture |
| `tests/test_extraction.py`, `test_decoupage.py`, `test_prompt.py`, `test_ollama.py`, `test_candidats.py`, `test_sortie.py`, `test_detection.py`, `test_cli_detecter.py`, `test_mesure.py` (créés) | tests |
| `README.md`, `../CLAUDE.md`, `../.gitignore` (modifiés) | documentation et exclusion git |

---

### Task 1: Répartition par extension partagée et extraction du texte

**Files:**
- Create: `src/obfuscation/formats/fichier.py`
- Create: `src/obfuscation/extraction.py`
- Modify: `src/obfuscation/cli.py` (imports, `EXTENSIONS_TEXTE`, `_transformer`, `main_obfusquer`)
- Test: `tests/test_extraction.py`

**Interfaces:**
- Consumes: `transformer_ooxml`, `pdf_vers_markdown`, `transformer_texte` (existants) ; `Table` ; `Remplacement`, `Sens` de `moteur.py`.
- Produces:
  - `obfuscation.formats.fichier.transformer_fichier(source: Path, moteur, sens: Sens) -> Resultat`
  - `obfuscation.formats.fichier.EXTENSIONS_TEXTE: set[str]`, `EXTENSIONS_LISIBLES: set[str]`
  - `obfuscation.extraction.extraire(source: Path) -> str`, qui lève `ErreurFichier` ou `OSError` comme `obfusquer`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_extraction.py` :

```python
import pytest
from documents import docx_exemple, pdf_exemple, pptx_exemple, xlsx_exemple

from obfuscation.erreurs import ErreurFichier
from obfuscation.extraction import extraire


def test_extrait_le_texte_d_un_docx_sans_le_modifier(tmp_path):
    chemin = tmp_path / "proposition.docx"
    chemin.write_bytes(docx_exemple())
    avant = chemin.read_bytes()
    texte = extraire(chemin)
    assert "Novaltis SA signe le Projet Héron." in texte  # segments de mise en forme réunis
    assert "Voir Novaltis" in texte  # note de bas de page
    assert "Novaltis – confidentiel" in texte  # en-tête
    assert "Validé par Jeanne Martin" in texte  # commentaire
    assert chemin.read_bytes() == avant


def test_extrait_cellules_commentaires_et_noms_de_feuilles(tmp_path):
    chemin = tmp_path / "classeur.xlsx"
    chemin.write_bytes(xlsx_exemple())
    lignes = extraire(chemin).splitlines()
    assert "Client Novaltis SA" in lignes
    assert "Novaltis" in lignes  # nom de la feuille
    assert "Validé par Jeanne Martin" in lignes


def test_extrait_diapositives_et_notes(tmp_path):
    chemin = tmp_path / "lancement.pptx"
    chemin.write_bytes(pptx_exemple())
    texte = extraire(chemin)
    assert "Novaltis pilote." in texte
    assert "Appeler Jeanne Martin" in texte


def test_extrait_un_pdf_et_un_texte(tmp_path):
    pdf = tmp_path / "contrat.pdf"
    pdf.write_bytes(pdf_exemple("<p>Contrat signé avec Novaltis.</p>"))
    assert "Novaltis" in extraire(pdf)
    note = tmp_path / "note.md"
    note.write_text("Le Projet Héron.\n", encoding="utf-8")
    assert extraire(note) == "Le Projet Héron.\n"


def test_fichier_illisible(tmp_path):
    chemin = tmp_path / "casse.docx"
    chemin.write_bytes(b"pas une archive")
    with pytest.raises(ErreurFichier):
        extraire(chemin)
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_extraction.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'obfuscation.extraction'`

- [ ] **Step 3: Créer `src/obfuscation/formats/fichier.py`**

```python
"""Répartition par extension : applique le moteur, ou tout objet qui en offre l'interface, au contenu d'un fichier."""
from pathlib import Path

from ..moteur import Moteur, Sens
from . import Resultat
from .ooxml import EXTENSIONS_OOXML, transformer_ooxml
from .pdf import pdf_vers_markdown
from .texte import transformer_texte

EXTENSIONS_TEXTE = {".md", ".txt"}
EXTENSIONS_LISIBLES = EXTENSIONS_OOXML | EXTENSIONS_TEXTE | {".pdf"}


def transformer_fichier(source: Path, moteur: Moteur, sens: Sens) -> Resultat:
    donnees = source.read_bytes()
    extension = source.suffix.lower()
    if extension in EXTENSIONS_OOXML:
        return transformer_ooxml(donnees, moteur, sens, str(source))
    if extension == ".pdf":
        donnees = pdf_vers_markdown(donnees, str(source)).encode("utf-8")
    return transformer_texte(donnees, moteur, sens, str(source))
```

- [ ] **Step 4: Adapter `src/obfuscation/cli.py`**

Remplacer les imports de formats :

```python
from .formats import Resultat
from .formats.fichier import EXTENSIONS_LISIBLES, EXTENSIONS_TEXTE, transformer_fichier
from .formats.ooxml import EXTENSIONS_OOXML
```

(supprimer `from .formats.pdf import pdf_vers_markdown` et `from .formats.texte import transformer_texte`).

Supprimer la ligne `EXTENSIONS_TEXTE = {".md", ".txt"}` et la fonction `_transformer` en entier. Dans `_traiter`, remplacer `resultat = _transformer(source, moteur, sens)` par :

```python
            resultat = transformer_fichier(source, moteur, sens)
```

Dans `main_obfusquer`, remplacer `EXTENSIONS_OOXML | EXTENSIONS_TEXTE | {".pdf"}` par `EXTENSIONS_LISIBLES`. `main_restaurer` garde `EXTENSIONS_OOXML | EXTENSIONS_TEXTE`.

- [ ] **Step 5: Créer `src/obfuscation/extraction.py`**

```python
"""Texte brut d'un fichier, lu par les adaptateurs de formats d'« obfusquer », sans rien remplacer."""
from pathlib import Path

from .formats.fichier import transformer_fichier
from .moteur import Remplacement, Sens
from .table import Table


class Collecteur:
    """Offre aux adaptateurs l'interface du moteur : enregistre chaque texte reçu et ne remplace rien.

    Les fichiers sont ainsi lus exactement comme « obfusquer » les lit : notes, commentaires, en-têtes, cellules,
    noms de feuilles, documents incorporés.
    """

    def __init__(self) -> None:
        self.textes: list[str] = []
        self.table = Table()
        self.avertissements: list[str] = []

    def remplacements(self, texte: str, sens: Sens) -> list[Remplacement]:
        self.textes.append(texte)
        return []

    def transformer(self, texte: str, sens: Sens) -> str:
        self.textes.append(texte)
        return texte


def extraire(source: Path) -> str:
    """Un texte par ligne (paragraphe, cellule, note…). Lève ErreurFichier ou OSError, comme « obfusquer »."""
    collecteur = Collecteur()
    transformer_fichier(source, collecteur, "obfusquer")
    return "\n".join(texte for texte in collecteur.textes if texte.strip())
```

- [ ] **Step 6: Vérifier que tout passe, y compris la suite existante**

Run: `uv run pytest -q`
Expected: tous les tests passent (131 existants + 5 nouveaux).

Si une assertion de `test_extraction.py` échoue parce qu'un texte arrive découpé autrement (par exemple l'en-tête Excel), afficher `extraire(...)` pour voir comment le texte arrive. Corriger l'assertion seulement si le texte est bien présent sous une autre forme. Si le texte est absent, c'est un défaut à signaler.

- [ ] **Step 7: Commit**

```bash
git add src/obfuscation/formats/fichier.py src/obfuscation/extraction.py src/obfuscation/cli.py tests/test_extraction.py
git commit -m "feat(obfuscation): extrait le texte des documents via les adaptateurs existants

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Découpage en morceaux

**Files:**
- Create: `src/obfuscation/detection/__init__.py` (vide à ce stade : une ligne de docstring)
- Create: `src/obfuscation/detection/decoupage.py`
- Test: `tests/test_decoupage.py`

**Interfaces:**
- Produces: `obfuscation.detection.decoupage.decouper(texte: str, taille: int = TAILLE) -> list[str]`, `TAILLE = 8000`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_decoupage.py` :

```python
from obfuscation.detection.decoupage import decouper


def test_texte_court_un_seul_morceau():
    assert decouper("Un.\nDeux.") == ["Un.\nDeux."]


def test_lignes_vides_ignorees():
    assert decouper("\n\nUn.\n\n  \nDeux.\n") == ["Un.\nDeux."]
    assert decouper("  \n") == []


def test_coupe_aux_paragraphes_avec_chevauchement():
    paragraphes = [f"Paragraphe {i} " + "x" * 30 for i in range(10)]  # 43 caractères chacun
    morceaux = decouper("\n".join(paragraphes), taille=100)
    assert len(morceaux) == 9
    assert all(len(m) <= 100 for m in morceaux)
    for p in paragraphes:
        assert any(p in m.split("\n") for m in morceaux)
    for avant, apres in zip(morceaux, morceaux[1:]):
        assert apres.split("\n")[0] == avant.split("\n")[-1]  # le dernier paragraphe ouvre le morceau suivant


def test_paragraphe_trop_long_coupe_en_fin_de_phrase():
    texte = ("Le prestataire livre le rapport. " * 10).strip()
    morceaux = decouper(texte, taille=100)
    assert all(len(m) <= 100 for m in morceaux)
    assert all(m.endswith(".") for m in morceaux)
    assert " ".join(morceaux).split() == texte.split()


def test_sans_fin_de_phrase_coupe_sur_une_espace():
    texte = ("mot " * 50).strip()
    morceaux = decouper(texte, taille=100)
    assert all(len(m) <= 100 for m in morceaux)
    assert " ".join(morceaux).split() == texte.split()


def test_sans_espace_coupe_net():
    assert decouper("x" * 250, taille=100) == ["x" * 100, "x" * 100, "x" * 50]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_decoupage.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'obfuscation.detection'`

- [ ] **Step 3: Implémenter**

`src/obfuscation/detection/__init__.py` :

```python
"""Détection des termes sensibles par un LLM local : du texte des documents au dictionnaire candidat."""
```

`src/obfuscation/detection/decoupage.py` :

```python
"""Découpage du texte en morceaux : un modèle de 8 milliards de paramètres est plus fiable sur un texte court."""
import re

TAILLE = 8000  # environ 2 000 tokens, à 4 caractères par token
FIN_DE_PHRASE = re.compile(r"(?<=[.!?…])\s+")


def _couper(paragraphe: str, taille: int) -> list[str]:
    """Un paragraphe trop long est coupé en fin de phrase, à défaut sur une espace, à défaut net."""
    morceaux = []
    while len(paragraphe) > taille:
        coupe = max((m.end() for m in FIN_DE_PHRASE.finditer(paragraphe, 0, taille)), default=0)
        if coupe == 0:
            coupe = paragraphe.rfind(" ", 0, taille) + 1 or taille
        morceaux.append(paragraphe[:coupe].strip())
        paragraphe = paragraphe[coupe:].lstrip()
    morceaux.append(paragraphe)
    return morceaux


def decouper(texte: str, taille: int = TAILLE) -> list[str]:
    """Morceaux d'au plus `taille` caractères, coupés aux fins de paragraphe.

    Le dernier paragraphe d'un morceau ouvre le suivant (quand la place le permet) : une entité à cheval sur deux
    morceaux n'est pas perdue.
    """
    paragraphes = [p for ligne in texte.splitlines() if ligne.strip() for p in _couper(ligne.strip(), taille)]
    morceaux: list[str] = []
    courant: list[str] = []
    for paragraphe in paragraphes:
        if courant and len("\n".join([*courant, paragraphe])) > taille:
            morceaux.append("\n".join(courant))
            dernier = courant[-1]
            courant = [dernier] if len(dernier) + 1 + len(paragraphe) <= taille else []
        courant.append(paragraphe)
    if courant:
        morceaux.append("\n".join(courant))
    return morceaux
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_decoupage.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add src/obfuscation/detection/__init__.py src/obfuscation/detection/decoupage.py tests/test_decoupage.py
git commit -m "feat(obfuscation): découpe le texte en morceaux pour le modèle local

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Prompt et schéma de réponse

**Files:**
- Create: `src/obfuscation/detection/prompt.py`
- Test: `tests/test_prompt.py`

**Interfaces:**
- Produces: `message_systeme(categories: list[str]) -> str`, `schema(categories: list[str]) -> dict`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_prompt.py` :

```python
import json

from obfuscation.detection.prompt import message_systeme, schema


def test_schema_limite_les_categories():
    s = schema(["CLIENT", "PERSONNE"])
    element = s["properties"]["entites"]["items"]
    assert element["properties"]["categorie"]["enum"] == ["CLIENT", "PERSONNE"]
    assert element["required"] == ["terme", "categorie"]
    assert s["required"] == ["entites"]


def test_message_definit_les_categories_demandees_seulement():
    message = message_systeme(["CLIENT", "PERSONNE"])
    assert "- CLIENT : " in message
    assert "- PERSONNE : " in message
    assert "LIEU" not in message  # ni dans les définitions ni dans l'exemple


def test_categorie_inconnue_recoit_une_definition_generique():
    assert "- SITE : nom propre relevant de la catégorie SITE" in message_systeme(["SITE"])


def test_exemple_valide_et_etranger_au_corpus_heron():
    message = message_systeme(["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"])
    reponse = json.loads(message.split("Réponse : ", 1)[1])
    assert {e["categorie"] for e in reponse["entites"]} == {"CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"}
    for terme in ("Novaltis", "Acme", "Héron", "Jeanne Martin"):
        assert terme not in message
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: FAIL avec `ModuleNotFoundError`

- [ ] **Step 3: Implémenter `src/obfuscation/detection/prompt.py`**

```python
"""Message système et schéma de réponse demandés au modèle local."""
import json

DEFINITIONS = {
    "CLIENT": "organisation cliente, pour qui le travail est réalisé",
    "PRESTATAIRE": "entreprise qui réalise la prestation, ou sous-traitant",
    "PROJET": "nom propre d'un projet, d'un programme ou d'un produit",
    "PERSONNE": "nom d'une personne (prénom et nom, ou nom seul)",
    "LIEU": "ville, site, adresse ou bâtiment nommé",
}
# Exemple inventé, volontairement étranger au corpus Héron : la mesure ne doit pas être faussée.
EXEMPLE_TEXTE = (
    "Le Groupe Valmont a confié à Bellerive Conseil le programme Atlas. "
    "Marc Dubreuil, chef de projet, se rendra à Lorient. Le client valide chaque livrable."
)
EXEMPLE_ENTITES = [
    ("Groupe Valmont", "CLIENT"),
    ("Bellerive Conseil", "PRESTATAIRE"),
    ("Atlas", "PROJET"),
    ("Marc Dubreuil", "PERSONNE"),
    ("Lorient", "LIEU"),
]


def schema(categories: list[str]) -> dict:
    """Schéma JSON imposé à la réponse (champ « format » d'Ollama) : l'enum interdit toute catégorie inventée."""
    entite = {
        "type": "object",
        "properties": {"terme": {"type": "string"}, "categorie": {"type": "string", "enum": list(categories)}},
        "required": ["terme", "categorie"],
    }
    return {"type": "object", "properties": {"entites": {"type": "array", "items": entite}}, "required": ["entites"]}


def message_systeme(categories: list[str]) -> str:
    definitions = [f"- {c} : {DEFINITIONS.get(c, f'nom propre relevant de la catégorie {c}')}" for c in categories]
    exemple = {"entites": [{"terme": t, "categorie": c} for t, c in EXEMPLE_ENTITES if c in categories]}
    return "\n".join([
        "Tu repères les entités nommées sensibles d'un document professionnel, pour les masquer avant tout partage.",
        "Catégories :",
        *definitions,
        "",
        "Règles :",
        "- Recopie chaque terme exactement comme il est écrit dans le texte, sans le corriger ni le traduire.",
        "- Uniquement des noms propres : jamais de nom commun ni d'expression générique "
        "(« le client », « la société », « le projet »).",
        "- Une entrée par forme rencontrée : si un nom apparaît sous deux formes, donne les deux.",
        "- N'invente rien : si le texte ne contient aucune entité, renvoie une liste vide.",
        "",
        f"Exemple. Texte : « {EXEMPLE_TEXTE} »",
        f"Réponse : {json.dumps(exemple, ensure_ascii=False)}",
    ])
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_prompt.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/obfuscation/detection/prompt.py tests/test_prompt.py
git commit -m "feat(obfuscation): rédige le prompt et le schéma de détection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Client Ollama

**Files:**
- Create: `src/obfuscation/detection/ollama.py`
- Create: `tests/faux_ollama.py`
- Modify: `tests/conftest.py` (ajout de la fixture `faux_ollama`)
- Test: `tests/test_ollama.py`

**Interfaces:**
- Consumes: `message_systeme`, `schema` (tâche 3) ; `ErreurConfiguration` (`erreurs.py`).
- Produces:
  - `class ErreurOllama(ErreurConfiguration)` : erreur fatale, code 2
  - `class ReponseInvalide(Exception)` : appel à retenter
  - `@dataclass(frozen=True) class Proposition: terme: str; categorie: str`
  - `class ClientOllama(url: str, modele: str, delai: float = 300.0)` avec `verifier() -> None` et `entites(texte: str, categories: list[str]) -> list[Proposition]`
  - Pour les tests : fixture `faux_ollama` (attributs `url`, `modeles: list[str]`, `reponses: list[tuple[int, dict | bytes, float]]`, `requetes: list[dict]`) et `faux_ollama.reponse_chat(entites: list[dict]) -> dict`

- [ ] **Step 1: Écrire le faux serveur et sa fixture**

`tests/faux_ollama.py` :

```python
"""Faux serveur Ollama : /api/tags liste des modèles, /api/chat renvoie les réponses programmées, dans l'ordre."""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def reponse_chat(entites: list[dict]) -> dict:
    return {"message": {"role": "assistant", "content": json.dumps({"entites": entites})}, "done": True}


class FauxOllama:
    def __init__(self) -> None:
        self.modeles = ["granite4.2:8b"]
        self.reponses: list[tuple[int, dict | bytes, float]] = []  # (code HTTP, corps, attente en secondes)
        self.requetes: list[dict] = []
        etat = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _repondre(self, code: int, corps: dict | bytes) -> None:
                donnees = corps if isinstance(corps, bytes) else json.dumps(corps).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

            def do_GET(self) -> None:
                self._repondre(200, {"models": [{"name": nom} for nom in etat.modeles]})

            def do_POST(self) -> None:
                etat.requetes.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                code, corps, attente = etat.reponses.pop(0)
                time.sleep(attente)
                self._repondre(code, corps)

        self._serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self._serveur.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._serveur.server_address[1]}"

    def demarrer(self) -> None:
        threading.Thread(target=self._serveur.serve_forever, daemon=True).start()

    def arreter(self) -> None:
        self._serveur.shutdown()
        self._serveur.server_close()
```

Ajouter à `tests/conftest.py` (en plus de l'existant) :

```python
from faux_ollama import FauxOllama


@pytest.fixture
def faux_ollama():
    serveur = FauxOllama()
    serveur.demarrer()
    yield serveur
    serveur.arreter()
```

- [ ] **Step 2: Écrire les tests qui échouent**

`tests/test_ollama.py` :

```python
import pytest
from faux_ollama import reponse_chat

from obfuscation.detection.ollama import ClientOllama, ErreurOllama, Proposition, ReponseInvalide

CATEGORIES = ["CLIENT", "PERSONNE"]


def test_envoie_modele_schema_et_temperature_nulle(faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "CLIENT"}]), 0)]
    propositions = ClientOllama(faux_ollama.url, "granite4.2:8b").entites("Signé avec Novaltis.", CATEGORIES)
    assert propositions == [Proposition("Novaltis", "CLIENT")]
    requete = faux_ollama.requetes[0]
    assert requete["model"] == "granite4.2:8b"
    assert requete["stream"] is False
    assert requete["options"]["temperature"] == 0
    assert requete["format"]["properties"]["entites"]["items"]["properties"]["categorie"]["enum"] == CATEGORIES
    assert requete["messages"][0]["role"] == "system"
    assert requete["messages"][1] == {"role": "user", "content": "Signé avec Novaltis."}


def test_verifier_accepte_le_modele(faux_ollama):
    ClientOllama(faux_ollama.url, "granite4.2:8b").verifier()


def test_verifier_accepte_un_nom_sans_etiquette(faux_ollama):
    faux_ollama.modeles = ["granite4.2:latest"]
    ClientOllama(faux_ollama.url, "granite4.2").verifier()


def test_verifier_signale_un_modele_absent(faux_ollama):
    with pytest.raises(ErreurOllama, match="ollama pull autre:1b"):
        ClientOllama(faux_ollama.url, "autre:1b").verifier()


def test_serveur_injoignable():
    with pytest.raises(ErreurOllama, match="docker compose up -d ollama"):
        ClientOllama("http://127.0.0.1:1", "granite4.2:8b").verifier()


def test_modele_introuvable_pendant_l_analyse(faux_ollama):
    faux_ollama.reponses = [(404, {"error": "model 'x' not found"}, 0)]
    with pytest.raises(ErreurOllama, match="ollama pull"):
        ClientOllama(faux_ollama.url, "x").entites("texte", CATEGORIES)


@pytest.mark.parametrize("corps", [
    {"message": {"content": "pas du json"}},
    {"message": {"content": '{"autre": []}'}},
    {"message": {"content": '{"entites": [{"terme": "X"}]}'}},
    {"inattendu": True},
    b"<html>pas du json</html>",
])
def test_reponse_non_conforme(faux_ollama, corps):
    faux_ollama.reponses = [(200, corps, 0)]
    with pytest.raises(ReponseInvalide):
        ClientOllama(faux_ollama.url, "granite4.2:8b").entites("texte", CATEGORIES)


def test_erreur_serveur(faux_ollama):
    faux_ollama.reponses = [(500, {"error": "out of memory"}, 0)]
    with pytest.raises(ReponseInvalide, match="500"):
        ClientOllama(faux_ollama.url, "granite4.2:8b").entites("texte", CATEGORIES)


def test_delai_depasse(faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([]), 1.0)]
    with pytest.raises(ReponseInvalide, match="pas de réponse"):
        ClientOllama(faux_ollama.url, "granite4.2:8b", delai=0.2).entites("texte", CATEGORIES)
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_ollama.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'obfuscation.detection.ollama'`

- [ ] **Step 4: Implémenter `src/obfuscation/detection/ollama.py`**

```python
"""Client minimal de l'API Ollama (/api/tags, /api/chat), sans dépendance."""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..erreurs import ErreurConfiguration
from .prompt import message_systeme, schema

DELAI_VERIFICATION = 10.0


class ErreurOllama(ErreurConfiguration):
    """Serveur injoignable ou modèle absent : rien ne peut être analysé."""


class ReponseInvalide(Exception):
    """Un appel a échoué (délai dépassé, réponse non conforme, erreur du serveur) : le morceau peut être retenté."""


@dataclass(frozen=True)
class Proposition:
    terme: str
    categorie: str


class ClientOllama:
    def __init__(self, url: str, modele: str, delai: float = 300.0):
        self.url = url.rstrip("/")
        self.modele = modele
        self.delai = delai

    def verifier(self) -> None:
        """Serveur joignable et modèle téléchargé ; « granite4.2 » désigne « granite4.2:latest »."""
        try:
            modeles = self._requete("/api/tags", delai=DELAI_VERIFICATION).get("models", [])
            noms = {m.get("name") for m in modeles}
        except (ReponseInvalide, AttributeError, TypeError) as e:
            raise ErreurOllama(f"le serveur {self.url} ne répond pas comme Ollama ({e})") from e
        if self.modele not in noms and f"{self.modele}:latest" not in noms:
            raise ErreurOllama(f"modèle « {self.modele} » absent du serveur Ollama {self.url} : ollama pull {self.modele}")

    def entites(self, texte: str, categories: list[str]) -> list[Proposition]:
        reponse = self._requete("/api/chat", {
            "model": self.modele,
            "stream": False,
            "format": schema(categories),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": message_systeme(categories)},
                {"role": "user", "content": texte},
            ],
        })
        try:
            entites = json.loads(reponse["message"]["content"])["entites"]
            return [Proposition(str(e["terme"]), str(e["categorie"])) for e in entites]
        except (KeyError, TypeError, ValueError) as e:
            raise ReponseInvalide("réponse du modèle non conforme au schéma") from e

    def _requete(self, chemin: str, corps: dict | None = None, delai: float | None = None) -> dict:
        delai = delai or self.delai
        donnees = None if corps is None else json.dumps(corps).encode("utf-8")
        requete = urllib.request.Request(self.url + chemin, data=donnees, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(requete, timeout=delai) as reponse:
                return json.loads(reponse.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErreurOllama(f"modèle « {self.modele} » introuvable sur {self.url} : ollama pull {self.modele}") from e
            raise ReponseInvalide(f"Ollama a répondu {e.code}") from e
        except TimeoutError as e:
            raise ReponseInvalide(f"pas de réponse d'Ollama en {delai:g} s") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ReponseInvalide(f"pas de réponse d'Ollama en {delai:g} s") from e
            raise ErreurOllama(
                f"Ollama injoignable à {self.url} ({e.reason}) ; pour la stack locale, depuis local-llm/ : "
                "docker compose up -d ollama"
            ) from e
        except OSError as e:  # connexion coupée en cours de réponse (modèle arrêté, mémoire saturée…)
            raise ReponseInvalide(f"connexion à Ollama interrompue ({e})") from e
        except ValueError as e:  # JSON illisible
            raise ReponseInvalide("réponse d'Ollama illisible") from e
```

Note : `test_reponse_non_conforme` avec `{"inattendu": True}` passe par `reponse["message"]` → `KeyError` → `ReponseInvalide`. Le corps HTML passe par `json.loads` dans `_requete` → `ValueError` → `ReponseInvalide`.

- [ ] **Step 5: Vérifier**

Run: `uv run pytest tests/test_ollama.py -v`
Expected: 13 PASS (le test paramétré compte pour 5). Le test du délai peut afficher un `BrokenPipeError` du faux serveur sur la sortie d'erreur : c'est sans effet sur le résultat.

- [ ] **Step 6: Commit**

```bash
git add src/obfuscation/detection/ollama.py tests/faux_ollama.py tests/conftest.py tests/test_ollama.py
git commit -m "feat(obfuscation): ajoute le client Ollama de la détection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Post-traitement des propositions

**Files:**
- Create: `src/obfuscation/detection/candidats.py`
- Test: `tests/test_candidats.py`

**Interfaces:**
- Consumes: `Proposition` (tâche 4) ; `AVANT`, `APRES`, `Dictionnaire`, `motif_de_terme`, `normaliser` (`dictionnaire.py`).
- Produces:
  - `@dataclass class Candidat: categorie: str; variantes: list[str]; occurrences: int = 0; contexte: str = ""; presumees: list[str]; autres_categories: list[str]`, avec la propriété `toutes -> list[str]` (variantes puis présumées)
  - `class Collecte(categories: list[str], exclus: Dictionnaire)` avec `ajouter(propositions: list[Proposition], morceau: str) -> None`, `candidats(texte: str) -> list[Candidat]` et les compteurs `rejetees: int`, `ecartees: int`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_candidats.py` :

```python
from obfuscation.detection.candidats import Collecte
from obfuscation.detection.ollama import Proposition as P
from obfuscation.dictionnaire import Dictionnaire, charger_dictionnaires

CATEGORIES = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]


def collecte(exclus=None, categories=CATEGORIES):
    return Collecte(list(categories), exclus or Dictionnaire())


def un_seul(c, texte):
    candidats = c.candidats(texte)
    assert len(candidats) == 1
    return candidats[0]


def test_terme_absent_du_texte_rejete():
    c = collecte()
    c.ajouter([P("Novaltys", "CLIENT")], "Signé avec Novaltis.")
    assert c.candidats("Signé avec Novaltis.") == []
    assert c.rejetees == 1


def test_terme_coupe_dans_un_mot_rejete():
    c = collecte()
    c.ajouter([P("Nova", "CLIENT")], "Signé avec Novaltis.")
    assert c.candidats("Signé avec Novaltis.") == []
    assert c.rejetees == 1


def test_forme_du_texte_conservee():
    c = collecte()
    texte = "Contrat L’Oréal Luxe signé."
    c.ajouter([P("l'oréal  luxe", "CLIENT")], texte)  # casse, apostrophe droite, espaces doublées
    assert un_seul(c, texte).variantes == ["L’Oréal Luxe"]


def test_filtrage_des_termes_courts_numeriques_et_generiques():
    c = collecte()
    texte = "Le Client SA, 2026."
    c.ajouter([P("SA", "CLIENT"), P("2026", "PROJET"), P("Client", "CLIENT")], texte)
    assert c.candidats(texte) == []
    assert c.ecartees == 3


def test_categorie_non_demandee_ecartee():
    c = collecte(categories=["CLIENT"])
    c.ajouter([P("Lyon", "LIEU")], "Réunion à Lyon.")
    assert c.candidats("Réunion à Lyon.") == []
    assert c.ecartees == 1


def test_termes_deja_connus_exclus(tmp_path):
    chemin = tmp_path / "client.yaml"
    chemin.write_text("CLIENT:\n  - Novaltis\n", encoding="utf-8")
    c = collecte(exclus=charger_dictionnaires([chemin]))
    c.ajouter([P("NOVALTIS", "PRESTATAIRE")], "Signé par NOVALTIS.")
    assert c.candidats("Signé par NOVALTIS.") == []
    assert c.ecartees == 1


def test_fusion_des_variantes_accentuees():
    c = collecte()
    premier, second = "Acme Défense signe. Acme Défense paie.", "Acme Defense valide."
    c.ajouter([P("Acme Défense", "CLIENT")], premier)
    c.ajouter([P("Acme Defense", "CLIENT")], second)
    candidat = un_seul(c, premier + "\n" + second)
    assert candidat.variantes == ["Acme Défense", "Acme Defense"]  # la plus fréquente d'abord
    assert candidat.occurrences == 3


def test_terme_inclus_devient_variante_presumee():
    c = collecte()
    texte = "Acme Défense signe. Acme paie."
    c.ajouter([P("Acme", "CLIENT"), P("Acme Défense", "CLIENT")], texte)
    candidat = un_seul(c, texte)
    assert candidat.variantes == ["Acme Défense"]
    assert candidat.presumees == ["Acme"]
    assert candidat.toutes == ["Acme Défense", "Acme"]
    assert candidat.occurrences == 2


def test_inclusion_par_mots_entiers_seulement():
    c = collecte()
    texte = "Acme et Acmeon Group."
    c.ajouter([P("Acme", "CLIENT"), P("Acmeon Group", "CLIENT")], texte)
    assert len(c.candidats(texte)) == 2


def test_inclusion_dans_la_meme_categorie_seulement():
    c = collecte()
    texte = "Le Projet Héron est mené par Héron Conseil."
    c.ajouter([P("Héron", "PROJET"), P("Héron Conseil", "PRESTATAIRE")], texte)
    assert len(c.candidats(texte)) == 2


def test_conflit_de_categorie_tranche_a_la_majorite():
    c = collecte()
    texte = "Novaltis réalise la prestation."
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "CLIENT")], texte)
    candidat = un_seul(c, texte)
    assert candidat.categorie == "PRESTATAIRE"
    assert candidat.autres_categories == ["CLIENT"]


def test_egalite_tranchee_par_l_ordre_des_categories():
    c = collecte()
    texte = "Novaltis réalise la prestation."
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "CLIENT")], texte)
    assert un_seul(c, texte).categorie == "CLIENT"


def test_ordre_et_contexte():
    c = collecte()
    texte = "x" * 100 + " Jeanne Martin écrit à Paul Durand. Jeanne Martin relance. " + "y" * 100
    c.ajouter([P("Paul Durand", "PERSONNE"), P("Jeanne Martin", "PERSONNE")], texte)
    candidats = c.candidats(texte)
    assert [k.variantes[0] for k in candidats] == ["Jeanne Martin", "Paul Durand"]  # par occurrences décroissantes
    contexte = candidats[0].contexte
    assert contexte.startswith("…") and contexte.endswith("…")
    assert "Jeanne Martin" in contexte
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_candidats.py -v`
Expected: FAIL avec `ModuleNotFoundError`

- [ ] **Step 3: Implémenter `src/obfuscation/detection/candidats.py`**

```python
"""Post-traitement déterministe des propositions du modèle : rien n'est proposé qui ne figure dans le texte."""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..dictionnaire import APRES, AVANT, Dictionnaire, motif_de_terme, normaliser
from .ollama import Proposition

LONGUEUR_MIN = 3
CONTEXTE = 40  # caractères de part et d'autre de la première occurrence
MOTS_GENERIQUES = frozenset(normaliser(mot) for mot in (
    "client", "clients", "société", "entreprise", "prestataire", "fournisseur", "titulaire", "partenaire",
    "projet", "programme", "direction", "équipe", "service", "département", "groupe", "comité de pilotage",
))


@dataclass
class Candidat:
    categorie: str
    variantes: list[str]  # la première est celle que « restaurer » remettra en place
    occurrences: int = 0
    contexte: str = ""
    presumees: list[str] = field(default_factory=list)  # termes inclus dans une variante : à vérifier
    autres_categories: list[str] = field(default_factory=list)

    @property
    def toutes(self) -> list[str]:
        return [*self.variantes, *self.presumees]


def _recherche(termes: list[str]) -> re.Pattern:
    """Mêmes règles de correspondance que les dictionnaires ; les plus longs termes d'abord."""
    alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
    return re.compile(rf"{AVANT}(?:{alternatives}){APRES}", re.IGNORECASE)


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", normaliser(texte)) if not unicodedata.combining(c))


def _contient(long: str, court: str) -> bool:
    return long != court and re.search(rf"(?<!\w){re.escape(court)}(?!\w)", long) is not None


class Collecte:
    def __init__(self, categories: list[str], exclus: Dictionnaire):
        self.categories = categories
        self.exclus = exclus
        self.rejetees = 0  # propositions absentes du texte : inventées ou déformées par le modèle
        self.ecartees = 0  # filtrées, hors des catégories demandées, ou déjà dans un dictionnaire
        self._votes: dict[str, Counter] = defaultdict(Counter)  # clé normalisée → catégories proposées
        self._formes: dict[str, Counter] = defaultdict(Counter)  # clé normalisée → formes trouvées dans le texte

    def ajouter(self, propositions: list[Proposition], morceau: str) -> None:
        for proposition in propositions:
            terme = " ".join(proposition.terme.split())
            if (
                proposition.categorie not in self.categories
                or len(terme) < LONGUEUR_MIN
                or not any(c.isalpha() for c in terme)
                or normaliser(terme) in MOTS_GENERIQUES
            ):
                self.ecartees += 1
                continue
            trouve = _recherche([terme]).search(morceau)
            if trouve is None:
                self.rejetees += 1
                continue
            forme = " ".join(trouve.group().split())  # la forme du texte, pas celle du modèle
            if self.exclus.terme(forme) is not None:
                self.ecartees += 1
                continue
            cle = normaliser(forme)
            self._votes[cle][proposition.categorie] += 1
            self._formes[cle][forme] += 1

    def candidats(self, texte: str) -> list[Candidat]:
        """`texte` : l'ensemble des documents, pour compter les occurrences et citer un contexte."""
        rang = {c: i for i, c in enumerate(self.categories)}
        entrees = []
        for cle, votes in self._votes.items():
            classement = sorted(votes, key=lambda c: (-votes[c], rang[c]))
            forme = self._formes[cle].most_common(1)[0][0]
            entrees.append(Candidat(classement[0], [forme], autres_categories=classement[1:]))
        entrees = _fusionner_inclus(_fusionner_accents(entrees))
        for candidat in entrees:
            _compter(candidat, texte)
        return sorted(entrees, key=lambda c: (rang[c.categorie], -c.occurrences, c.variantes[0]))


def _ajouter_categories(cible: Candidat, source: Candidat) -> None:
    cible.autres_categories += [c for c in source.autres_categories if c not in cible.autres_categories]


def _fusionner_accents(entrees: list[Candidat]) -> list[Candidat]:
    """« Acme Défense » et « Acme Defense » : une entrée, deux variantes."""
    groupes: dict[tuple[str, str], Candidat] = {}
    for entree in entrees:
        cle = (entree.categorie, _sans_accents(entree.variantes[0]))
        if cle in groupes:
            groupes[cle].variantes += entree.variantes
            _ajouter_categories(groupes[cle], entree)
        else:
            groupes[cle] = entree
    return list(groupes.values())


def _fusionner_inclus(entrees: list[Candidat]) -> list[Candidat]:
    """« Acme », contenu par mots entiers dans « Acme Défense » (même catégorie), en devient une variante présumée.

    Du plus court au plus long : un terme rejoint le plus court de ceux qui le contiennent, et le suit si celui-ci
    est à son tour inclus dans un terme plus long.
    """
    restants = sorted(entrees, key=lambda e: len(e.variantes[0]))
    resultat = []
    for i, court in enumerate(restants):
        hote = next((
            long for long in restants[i + 1:]
            if long.categorie == court.categorie
            and any(_contient(_sans_accents(l), _sans_accents(c)) for l in long.variantes for c in court.variantes)
        ), None)
        if hote is None:
            resultat.append(court)
        else:
            hote.presumees += court.toutes
            _ajouter_categories(hote, court)
    return resultat


def _compter(candidat: Candidat, texte: str) -> None:
    comptes = {v: len(_recherche([v]).findall(texte)) for v in candidat.variantes}
    candidat.variantes.sort(key=lambda v: (-comptes[v], v))
    trouves = list(_recherche(candidat.toutes).finditer(texte))
    candidat.occurrences = len(trouves)
    if trouves:
        debut, fin = max(0, trouves[0].start() - CONTEXTE), trouves[0].end() + CONTEXTE
        extrait = " ".join(texte[debut:fin].split())
        candidat.contexte = ("…" if debut > 0 else "") + extrait + ("…" if fin < len(texte) else "")
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_candidats.py -v`
Expected: 13 PASS

- [ ] **Step 5: Commit**

```bash
git add src/obfuscation/detection/candidats.py tests/test_candidats.py
git commit -m "feat(obfuscation): vérifie, filtre et fusionne les termes proposés par le modèle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Écriture du dictionnaire candidat

**Files:**
- Create: `src/obfuscation/detection/sortie.py`
- Test: `tests/test_sortie.py`

**Interfaces:**
- Consumes: `Candidat` (tâche 5) ; `charger_dictionnaires` (`dictionnaire.py`).
- Produces:
  - `rendre(candidats: list[Candidat], categories: list[str], modele: str, ignores: list[str], jour: date | None = None) -> str`
  - `ecrire(chemin: Path, contenu: str) -> None`, qui lève `FileExistsError` si `chemin` existe

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_sortie.py` :

```python
from datetime import date

import pytest

from obfuscation.detection.candidats import Candidat
from obfuscation.detection.sortie import ecrire, rendre
from obfuscation.dictionnaire import charger_dictionnaires


def test_yaml_commente_et_chargeable_par_obfusquer(tmp_path):
    candidats = [
        Candidat("CLIENT", ["Acme Défense", "Acme Defense"], 3, "…signé par Acme Défense pour…", ["Acme"]),
        Candidat("PERSONNE", ["Jeanne Martin"], 1, "…par Jeanne Martin…", autres_categories=["CLIENT"]),
    ]
    contenu = rendre(candidats, ["CLIENT", "PROJET", "PERSONNE"], "granite4.2:8b", [], date(2026, 10, 8))
    assert contenu.splitlines()[0] == (
        "# Dictionnaire candidat produit par « detecter » le 2026-10-08 (modèle granite4.2:8b)."
    )
    assert "# Morceaux non analysés : aucun." in contenu
    assert "  - [Acme Défense, Acme Defense, Acme]  # 3 occurrences ; variante présumée, à vérifier : Acme" in contenu
    assert "    # « …signé par Acme Défense pour… »" in contenu
    assert "  - Jeanne Martin  # 1 occurrence ; aussi proposé en CLIENT" in contenu
    assert "# PROJET : aucun candidat" in contenu
    chemin = tmp_path / "client.candidats.yaml"
    ecrire(chemin, contenu)
    dictionnaire = charger_dictionnaires([chemin])
    assert dictionnaire.terme("Acme").canonique == "Acme Défense"
    assert dictionnaire.terme("Jeanne Martin").categorie == "PERSONNE"


@pytest.mark.parametrize("terme", ["R&D: Lyon", "#Héron", "'Atlas'", "Dupont, Fils", "[Projet] X", "Dupont & Fils", "true"])
def test_caracteres_speciaux(tmp_path, terme):
    contenu = rendre([Candidat("PROJET", [terme, terme + " Bis"], 1)], ["PROJET"], "m", [])
    chemin = tmp_path / "c.candidats.yaml"
    ecrire(chemin, contenu)
    dictionnaire = charger_dictionnaires([chemin])
    assert dictionnaire.terme(terme).canonique == terme


def test_morceaux_ignores_dans_l_en_tete(tmp_path):
    contenu = rendre([], ["CLIENT"], "m", ["a.docx — morceau 2/5", "b.md — morceau 1/1"])
    assert "# Morceaux non analysés : a.docx — morceau 2/5, b.md — morceau 1/1." in contenu
    chemin = tmp_path / "vide.candidats.yaml"
    ecrire(chemin, contenu)
    assert charger_dictionnaires([chemin]).variantes == []


def test_refuse_d_ecraser(tmp_path):
    chemin = tmp_path / "relu.candidats.yaml"
    chemin.write_text("CLIENT:\n  - Novaltis\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ecrire(chemin, rendre([], ["CLIENT"], "m", []))
    assert chemin.read_text(encoding="utf-8") == "CLIENT:\n  - Novaltis\n"
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_sortie.py -v`
Expected: FAIL avec `ModuleNotFoundError`

- [ ] **Step 3: Implémenter `src/obfuscation/detection/sortie.py`**

```python
"""Écriture du dictionnaire candidat : YAML au format des dictionnaires, commenté pour la relecture."""
import json
import re
from datetime import date
from pathlib import Path

from ..dictionnaire import charger_dictionnaires
from .candidats import Candidat

# Termes écrits sans guillemets : une lettre d'abord, puis lettres, chiffres, espaces et ponctuation sans effet en
# YAML (y compris dans une liste [a, b]). Tout le reste est écrit entre guillemets, échappé comme en JSON.
SIMPLE = re.compile(r"[^\W\d_][\w .'’&-]*")


def _scalaire(terme: str) -> str:
    return terme if SIMPLE.fullmatch(terme) else json.dumps(terme, ensure_ascii=False)


def _entree(candidat: Candidat) -> str:
    termes = [_scalaire(t) for t in candidat.toutes]
    return termes[0] if len(termes) == 1 else "[" + ", ".join(termes) + "]"


def _pluriel(nombre: int, mot: str) -> str:
    return mot + ("s" if nombre > 1 else "")


def _commentaire(candidat: Candidat) -> str:
    morceaux = [f"{candidat.occurrences} {_pluriel(candidat.occurrences, 'occurrence')}"]
    if candidat.presumees:
        n = len(candidat.presumees)
        morceaux.append(f"{_pluriel(n, 'variante')} {_pluriel(n, 'présumée')}, à vérifier : {', '.join(candidat.presumees)}")
    if candidat.autres_categories:
        morceaux.append(f"aussi proposé en {', '.join(candidat.autres_categories)}")
    return " ; ".join(morceaux)


def rendre(candidats: list[Candidat], categories: list[str], modele: str, ignores: list[str], jour: date | None = None) -> str:
    lignes = [
        f"# Dictionnaire candidat produit par « detecter » le {(jour or date.today()).isoformat()} (modèle {modele}).",
        "# À relire : supprimer les lignes refusées, corriger les catégories. Rien n'est appliqué sans « obfusquer ».",
        f"# Morceaux non analysés : {', '.join(ignores) if ignores else 'aucun'}.",
    ]
    for categorie in categories:
        retenus = [c for c in candidats if c.categorie == categorie]
        if not retenus:
            lignes.append(f"# {categorie} : aucun candidat")
            continue
        lignes.append(f"{categorie}:")
        for candidat in retenus:
            lignes.append(f"  - {_entree(candidat)}  # {_commentaire(candidat)}")
            if candidat.contexte:
                lignes.append(f"    # « {candidat.contexte} »")
    return "\n".join(lignes) + "\n"


def ecrire(chemin: Path, contenu: str) -> None:
    """Création exclusive : un candidat déjà relu n'est jamais écrasé. Le fichier est ensuite relu comme le ferait
    « obfusquer » ; un échec ici est un défaut de « rendre », et le fichier est laissé en place pour l'examiner."""
    with chemin.open("x", encoding="utf-8") as fichier:
        fichier.write(contenu)
    charger_dictionnaires([chemin])
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_sortie.py -v`
Expected: 10 PASS (le test paramétré compte pour 7)

- [ ] **Step 5: Commit**

```bash
git add src/obfuscation/detection/sortie.py tests/test_sortie.py
git commit -m "feat(obfuscation): écrit le dictionnaire candidat commenté

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Analyse de bout en bout et commande `detecter`

**Files:**
- Modify: `src/obfuscation/detection/__init__.py`
- Modify: `src/obfuscation/cli.py` (ajout de `main_detecter`)
- Modify: `pyproject.toml` (`[project.scripts]`)
- Test: `tests/test_detection.py`, `tests/test_cli_detecter.py`

**Interfaces:**
- Consumes: `decouper` (tâche 2), `ClientOllama`, `ErreurOllama`, `ReponseInvalide`, `Proposition` (tâche 4), `Collecte`, `Candidat` (tâche 5), `rendre`, `ecrire` (tâche 6), `extraire`, `EXTENSIONS_LISIBLES` (tâche 1), `_fichiers`, `_signaler`, codes de retour (`cli.py`), `CATEGORIE` (`dictionnaire.py`).
- Produces:
  - `obfuscation.detection.CATEGORIES_PAR_DEFAUT: list[str]`, `MODELE_PAR_DEFAUT: str`, `URL_PAR_DEFAUT: str`
  - `@dataclass class Bilan: candidats: list[Candidat]; rejetees: int; ignores: list[str]`
  - `analyser(documents: list[tuple[str, str]], client, categories: list[str], exclus: Dictionnaire, signaler: Callable[[str, str], None] = ...) -> Bilan`, où `client` est tout objet qui offre `entites(texte, categories)`
  - `obfuscation.cli.main_detecter(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Écrire les tests de l'analyse qui échouent**

`tests/test_detection.py` :

```python
import pytest

from obfuscation.detection import analyser
from obfuscation.detection.ollama import ErreurOllama, ReponseInvalide
from obfuscation.detection.ollama import Proposition as P
from obfuscation.dictionnaire import Dictionnaire

CATEGORIES = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]


class FauxClient:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def entites(self, texte, categories):
        self.appels.append(texte)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def test_retient_les_termes_presents():
    client = FauxClient([[P("Novaltis", "PRESTATAIRE"), P("Inventé", "CLIENT")]])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire())
    assert [c.variantes for c in bilan.candidats] == [["Novaltis"]]
    assert bilan.rejetees == 1
    assert bilan.ignores == []


def test_retente_une_fois():
    client = FauxClient([ReponseInvalide("délai"), [P("Novaltis", "PRESTATAIRE")]])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire())
    assert len(client.appels) == 2
    assert len(bilan.candidats) == 1
    assert bilan.ignores == []


def test_ignore_un_morceau_apres_deux_echecs():
    messages = []
    client = FauxClient([ReponseInvalide("délai"), ReponseInvalide("délai")])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire(), lambda n, m: messages.append((n, m)))
    assert bilan.ignores == ["a.md — morceau 1/1"]
    assert ("analyse", "a.md — morceau 1/1") in messages
    assert ("avertissement", "a.md — morceau 1/1 non analysé : délai") in messages


def test_document_sans_texte_aucun_appel():
    client = FauxClient([])
    bilan = analyser([("images.pptx", ""), ("vide.md", "  \n")], client, CATEGORIES, Dictionnaire())
    assert client.appels == []
    assert bilan.candidats == []


def test_ollama_injoignable_interrompt():
    client = FauxClient([ErreurOllama("injoignable")])
    with pytest.raises(ErreurOllama):
        analyser([("a.md", "texte")], client, CATEGORIES, Dictionnaire())
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_detection.py -v`
Expected: FAIL avec `ImportError: cannot import name 'analyser'`

- [ ] **Step 3: Implémenter `src/obfuscation/detection/__init__.py`**

```python
"""Détection des termes sensibles par un LLM local : du texte des documents au dictionnaire candidat."""
from collections.abc import Callable
from dataclasses import dataclass, field

from ..dictionnaire import Dictionnaire
from .candidats import Candidat, Collecte
from .decoupage import decouper
from .ollama import ReponseInvalide

CATEGORIES_PAR_DEFAUT = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]
MODELE_PAR_DEFAUT = "granite4.2:8b"
URL_PAR_DEFAUT = "http://127.0.0.1:11434"


@dataclass
class Bilan:
    candidats: list[Candidat]
    rejetees: int  # propositions absentes du texte
    ignores: list[str] = field(default_factory=list)  # « fichier — morceau i/n » non analysés


def analyser(
    documents: list[tuple[str, str]],
    client,
    categories: list[str],
    exclus: Dictionnaire,
    signaler: Callable[[str, str], None] = lambda niveau, message: None,
) -> Bilan:
    """documents : (nom affiché, texte). `client` offre entites(texte, categories) (ClientOllama ou substitut).

    Un morceau en échec est retenté une fois, puis ignoré. ErreurOllama (serveur perdu) interrompt l'analyse.
    """
    collecte = Collecte(categories, exclus)
    ignores = []
    for nom, texte in documents:
        morceaux = decouper(texte)
        for i, morceau in enumerate(morceaux, 1):
            etiquette = f"{nom} — morceau {i}/{len(morceaux)}"
            signaler("analyse", etiquette)
            for essai in (1, 2):
                try:
                    collecte.ajouter(client.entites(morceau, categories), morceau)
                    break
                except ReponseInvalide as e:
                    if essai == 2:
                        signaler("avertissement", f"{etiquette} non analysé : {e}")
                        ignores.append(etiquette)
    texte_complet = "\n".join(texte for _, texte in documents)
    return Bilan(collecte.candidats(texte_complet), collecte.rejetees, ignores)
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_detection.py -v`
Expected: 5 PASS

- [ ] **Step 5: Écrire les tests de la commande qui échouent**

`tests/test_cli_detecter.py` :

```python
import pytest
from documents import DICO
from faux_ollama import reponse_chat

from obfuscation import cli
from obfuscation.dictionnaire import charger_dictionnaires


@pytest.fixture
def espace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("Le Projet Héron, piloté par Novaltis.\n", encoding="utf-8")
    (tmp_path / "dico.yaml").write_text(DICO, encoding="utf-8")
    return tmp_path


def detecter(espace, faux_ollama, *options):
    return cli.main_detecter([
        str(espace / "docs"), "-o", str(espace / "client.candidats.yaml"), "--ollama-url", faux_ollama.url, *options,
    ])


def test_detecte_et_ecrit_un_candidat(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([
        {"terme": "Novaltis", "categorie": "PRESTATAIRE"},
        {"terme": "Projet Héron", "categorie": "PROJET"},
        {"terme": "Inventé SA", "categorie": "CLIENT"},
    ]), 0)]
    assert detecter(espace, faux_ollama) == 0
    dictionnaire = charger_dictionnaires([espace / "client.candidats.yaml"])
    assert dictionnaire.terme("Novaltis").categorie == "PRESTATAIRE"
    assert dictionnaire.terme("Projet Héron").categorie == "PROJET"
    assert dictionnaire.terme("Inventé SA") is None
    assert faux_ollama.requetes[0]["messages"][1]["content"] == "note.md\nLe Projet Héron, piloté par Novaltis."


def test_le_nom_du_fichier_est_analyse(espace, faux_ollama):
    (espace / "docs" / "note.md").unlink()
    (espace / "docs" / "Proposition Acme.md").write_text("Texte neutre.\n", encoding="utf-8")
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Acme", "categorie": "CLIENT"}]), 0)]
    assert detecter(espace, faux_ollama) == 0
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Acme").categorie == "CLIENT"


def test_exclut_les_termes_des_dictionnaires(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "CLIENT"}]), 0)]
    assert detecter(espace, faux_ollama, "-d", str(espace / "dico.yaml")) == 0
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).variantes == []


def test_refuse_une_sortie_existante(espace, faux_ollama):
    (espace / "client.candidats.yaml").write_text("CLIENT:\n  - Relu\n", encoding="utf-8")
    assert detecter(espace, faux_ollama) == 2
    assert (espace / "client.candidats.yaml").read_text(encoding="utf-8") == "CLIENT:\n  - Relu\n"
    assert faux_ollama.requetes == []


def test_ollama_injoignable(espace, capsys):
    code = cli.main_detecter([str(espace / "docs"), "-o", str(espace / "c.candidats.yaml"), "--ollama-url", "http://127.0.0.1:1"])
    assert code == 2
    assert not (espace / "c.candidats.yaml").exists()
    assert "docker compose up -d ollama" in capsys.readouterr().err


def test_modele_absent(espace, faux_ollama, capsys):
    assert detecter(espace, faux_ollama, "--modele", "autre:1b") == 2
    assert "ollama pull autre:1b" in capsys.readouterr().err


def test_categories_invalides(espace, faux_ollama):
    assert detecter(espace, faux_ollama, "--categories", "client,LIEU") == 2


def test_categories_personnalisees(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "SOCIETE"}]), 0)]
    assert detecter(espace, faux_ollama, "--categories", "SOCIETE") == 0
    assert faux_ollama.requetes[0]["format"]["properties"]["entites"]["items"]["properties"]["categorie"]["enum"] == ["SOCIETE"]
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Novaltis").categorie == "SOCIETE"


def test_morceau_non_analyse_code_1(espace, faux_ollama):
    invalide = (200, {"message": {"content": "pas du json"}}, 0)
    faux_ollama.reponses = [invalide, invalide]
    assert detecter(espace, faux_ollama) == 1
    contenu = (espace / "client.candidats.yaml").read_text(encoding="utf-8")
    assert "# Morceaux non analysés : note.md — morceau 1/1." in contenu


def test_fichier_illisible_code_1(espace, faux_ollama):
    (espace / "docs" / "casse.docx").write_bytes(b"pas une archive")
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "PRESTATAIRE"}]), 0)]
    assert detecter(espace, faux_ollama) == 1
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Novaltis") is not None
```

- [ ] **Step 6: Vérifier l'échec**

Run: `uv run pytest tests/test_cli_detecter.py -v`
Expected: FAIL avec `AttributeError: module 'obfuscation.cli' has no attribute 'main_detecter'`

- [ ] **Step 7: Implémenter `main_detecter` dans `src/obfuscation/cli.py`**

Ajouter aux imports :

```python
from .detection import CATEGORIES_PAR_DEFAUT, MODELE_PAR_DEFAUT, URL_PAR_DEFAUT, analyser
from .detection.ollama import ClientOllama, ErreurOllama
from .detection.sortie import ecrire, rendre
from .dictionnaire import CATEGORIE, Dictionnaire, charger_dictionnaires
from .extraction import extraire
```

(la ligne `from .dictionnaire import Dictionnaire, charger_dictionnaires` existante est remplacée par celle-ci).

Mettre à jour la docstring du module : `"""Commandes obfusquer, restaurer et detecter."""`

Ajouter à la fin du fichier :

```python
def _categories(texte: str) -> list[str]:
    categories = list(dict.fromkeys(c.strip() for c in texte.split(",") if c.strip()))
    if not categories or not all(CATEGORIE.fullmatch(c) for c in categories):
        raise ErreurConfiguration(f"catégories invalides : {texte} (majuscules, chiffres et _, séparées par des virgules)")
    return categories


def main_detecter(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="detecter",
        description="Propose un dictionnaire candidat à partir des entités repérées par un LLM local (Ollama). "
        "Rien ne quitte la machine.",
    )
    parseur.add_argument("chemins", nargs="+", type=Path, help="fichiers ou dossiers à analyser")
    parseur.add_argument("-o", "--sortie", required=True, type=Path, help="dictionnaire candidat à créer (jamais écrasé)")
    parseur.add_argument("-d", "--dictionnaire", action="append", default=[], type=Path,
                         help="dictionnaire existant, dont les termes ne sont pas reproposés (option répétable)")
    parseur.add_argument("--modele", default=MODELE_PAR_DEFAUT, help=f"modèle Ollama (défaut : {MODELE_PAR_DEFAUT})")
    parseur.add_argument("--ollama-url", default=URL_PAR_DEFAUT, help=f"serveur Ollama (défaut : {URL_PAR_DEFAUT})")
    parseur.add_argument("--categories", default=",".join(CATEGORIES_PAR_DEFAUT),
                         help="catégories recherchées, séparées par des virgules (défaut : %(default)s)")
    parseur.add_argument("--delai", type=float, default=300.0, help="délai maximal par appel au modèle, en secondes")
    args = parseur.parse_args(argv)
    try:
        categories = _categories(args.categories)
        if args.sortie.exists():
            raise ErreurConfiguration(f"{args.sortie} existe déjà : un dictionnaire candidat relu ne doit pas être écrasé")
        exclus = charger_dictionnaires(args.dictionnaire)
        client = ClientOllama(args.ollama_url, args.modele, args.delai)
        client.verifier()
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    code = SUCCES
    documents = []
    for source, relatif in _fichiers(args.chemins, args.sortie):
        if source.suffix.lower() not in EXTENSIONS_LISIBLES:
            _signaler("avertissement", f"{source} : format non pris en charge, ignoré")
            continue
        try:
            texte = extraire(source)
        except ErreurFichier as e:
            _signaler("erreur", str(e))
            code = ECHEC_FICHIERS
            continue
        except OSError as e:
            _signaler("erreur", f"{source} : lecture impossible ({e.strerror or e})")
            code = ECHEC_FICHIERS
            continue
        # Les noms de fichiers et de dossiers peuvent eux aussi contenir des termes sensibles.
        documents.append((str(relatif), "\n".join([*relatif.parts, texte])))
    try:
        bilan = analyser(documents, client, categories, exclus, _signaler)
    except ErreurOllama as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    ecrire(args.sortie, rendre(bilan.candidats, categories, args.modele, bilan.ignores))
    if bilan.ignores:
        code = ECHEC_FICHIERS
    print(
        f"Dictionnaire candidat : {args.sortie} ({len(bilan.candidats)} candidats ; {bilan.rejetees} propositions "
        f"absentes du texte, rejetées ; {len(bilan.ignores)} morceaux non analysés). À relire avant usage.",
        file=sys.stderr,
    )
    return code
```

`ErreurConfiguration` est déjà importée dans `cli.py` (`from .erreurs import ErreurConfiguration, ErreurFichier, ErreurTable`).

- [ ] **Step 8: Déclarer la commande dans `pyproject.toml`**

```toml
[project.scripts]
obfusquer = "obfuscation.cli:main_obfusquer"
restaurer = "obfuscation.cli:main_restaurer"
detecter = "obfuscation.cli:main_detecter"
```

Run: `uv sync && uv run detecter --help`
Expected: l'aide de `detecter` s'affiche.

- [ ] **Step 9: Vérifier toute la suite**

Run: `uv run pytest -q`
Expected: tous les tests passent.

- [ ] **Step 10: Commit**

```bash
git add src/obfuscation/detection/__init__.py src/obfuscation/cli.py pyproject.toml tests/test_detection.py tests/test_cli_detecter.py
git commit -m "feat(obfuscation): ajoute la commande detecter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Mesure du rappel et de la précision

**Files:**
- Create: `src/obfuscation/detection/mesure.py`
- Create: `exemples/mesurer.py`
- Test: `tests/test_mesure.py`

**Interfaces:**
- Consumes: `Candidat` (tâche 5) ; `Dictionnaire` (`recherche`, `terme()`) ; `analyser`, constantes (tâche 7) ; `ClientOllama`, `ErreurOllama` (tâche 4) ; `extraire`, `EXTENSIONS_LISIBLES` (tâche 1).
- Produces: `@dataclass(frozen=True) class Score` (`reference`, `trouvees`, `bonne_categorie`, `candidats`, `justes`, propriétés `rappel`, `precision`) ; `comparer(candidats: list[Candidat], reference: Dictionnaire, texte: str) -> Score`

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/test_mesure.py` :

```python
from obfuscation.detection.candidats import Candidat
from obfuscation.detection.mesure import comparer


def test_rappel_precision_et_categorie(dictionnaire):
    # dictionnaire (conftest) : CLIENT Novaltis…, PROJET Projet Héron / Héron / Heron, PERSONNE Jeanne Martin…
    texte = "Novaltis mène le Projet Héron."  # Jeanne Martin absente : hors de la référence
    candidats = [
        Candidat("PRESTATAIRE", ["Novaltis"]),  # trouvé, mauvaise catégorie
        Candidat("PROJET", ["Projet Héron"], presumees=["Héron"]),  # trouvé
        Candidat("LIEU", ["Lyon"]),  # fausse alerte
    ]
    score = comparer(candidats, dictionnaire, texte)
    assert (score.reference, score.trouvees, score.bonne_categorie) == (2, 2, 1)
    assert (score.candidats, score.justes) == (3, 2)
    assert score.rappel == 1.0
    assert score.precision == 2 / 3


def test_trouve_par_une_variante(dictionnaire):
    score = comparer([Candidat("CLIENT", ["NVL"])], dictionnaire, "Signé par Novaltis SA (NVL).")
    assert (score.reference, score.trouvees, score.bonne_categorie) == (1, 1, 1)


def test_rien_propose(dictionnaire):
    score = comparer([], dictionnaire, "Novaltis signe.")
    assert score.rappel == 0.0
    assert score.precision == 1.0
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_mesure.py -v`
Expected: FAIL avec `ModuleNotFoundError`

- [ ] **Step 3: Implémenter `src/obfuscation/detection/mesure.py`**

```python
"""Comparaison d'un résultat de détection à un dictionnaire de référence : des chiffres, jamais des termes."""
from dataclasses import dataclass

from ..dictionnaire import Dictionnaire, Terme
from .candidats import Candidat


@dataclass(frozen=True)
class Score:
    reference: int  # entrées de la référence présentes dans les documents
    trouvees: int  # dont au moins une variante a été proposée : un oubli est une fuite
    bonne_categorie: int  # trouvées dans la bonne catégorie
    candidats: int
    justes: int  # candidats dont une variante figure dans la référence

    @property
    def rappel(self) -> float:
        return self.trouvees / self.reference if self.reference else 1.0

    @property
    def precision(self) -> float:
        return self.justes / self.candidats if self.candidats else 1.0


def comparer(candidats: list[Candidat], reference: Dictionnaire, texte: str) -> Score:
    presentes: set[Terme] = set()
    if reference.recherche is not None:
        for m in reference.recherche.finditer(texte):
            terme = reference.terme(m.group(1))
            if terme is not None:
                presentes.add(terme)
    proposees: dict[Terme, set[str]] = {}  # entrée de référence → catégories sous lesquelles elle a été proposée
    justes = 0
    for candidat in candidats:
        termes = {reference.terme(v) for v in candidat.toutes} - {None}
        justes += bool(termes)
        for terme in termes:
            proposees.setdefault(terme, set()).add(candidat.categorie)
    trouvees = [t for t in presentes if t in proposees]
    return Score(
        reference=len(presentes),
        trouvees=len(trouvees),
        bonne_categorie=sum(t.categorie in proposees[t] for t in trouvees),
        candidats=len(candidats),
        justes=justes,
    )
```

- [ ] **Step 4: Vérifier**

Run: `uv run pytest tests/test_mesure.py -v`
Expected: 3 PASS

- [ ] **Step 5: Créer `exemples/mesurer.py`**

```python
"""Mesure de « detecter » : rappel et précision par rapport à un dictionnaire de référence.

Usage (depuis obfuscation/, Ollama démarré) :
    uv run python exemples/generer.py                    # une fois : documents du corpus fictif Héron
    uv run python exemples/mesurer.py                    # corpus Héron, 3 exécutions
    uv run python exemples/mesurer.py documents/ --reference client.yaml   # documents réels

Seuls des chiffres sont affichés, jamais un terme ni un nom de fichier : la sortie peut être partagée sans fuite.
"""
import argparse
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from obfuscation.detection import CATEGORIES_PAR_DEFAUT, MODELE_PAR_DEFAUT, URL_PAR_DEFAUT, analyser
from obfuscation.detection.mesure import comparer
from obfuscation.detection.ollama import ClientOllama, ErreurOllama
from obfuscation.dictionnaire import Dictionnaire, charger_dictionnaires
from obfuscation.erreurs import ErreurConfiguration, ErreurFichier
from obfuscation.extraction import extraire
from obfuscation.formats.fichier import EXTENSIONS_LISIBLES

ICI = Path(__file__).parent


class Chronometre:
    """Enveloppe le client pour cumuler le temps passé sur chaque document."""

    def __init__(self, client: ClientOllama):
        self.client = client
        self.document = ""
        self.durees: Counter = Counter()

    def entites(self, texte, categories):
        debut = time.perf_counter()
        try:
            return self.client.entites(texte, categories)
        finally:
            self.durees[self.document] += time.perf_counter() - debut

    def signaler(self, niveau: str, message: str) -> None:
        if niveau == "analyse":
            self.document = message.split(" — ")[0]


def documents(dossier: Path) -> list[tuple[str, str]]:
    """(« document n », texte) : les noms réels ne sont jamais affichés."""
    fichiers = sorted(
        f for f in dossier.rglob("*")
        if f.is_file() and f.suffix.lower() in EXTENSIONS_LISIBLES and not f.name.startswith("~$")
    )
    resultat = []
    for i, fichier in enumerate(fichiers, 1):
        try:
            resultat.append((f"document {i}", "\n".join([*fichier.relative_to(dossier).parts, extraire(fichier)])))
        except (ErreurFichier, OSError):
            print(f"document {i} illisible, ignoré", file=sys.stderr)
    return resultat


def main() -> int:
    parseur = argparse.ArgumentParser(description="Mesure le rappel et la précision de « detecter ».")
    parseur.add_argument("dossier", nargs="?", type=Path, default=ICI / "generes", help="documents à analyser")
    parseur.add_argument("--reference", type=Path, default=ICI / "dictionnaire.yaml", help="dictionnaire validé")
    parseur.add_argument("--modele", default=MODELE_PAR_DEFAUT)
    parseur.add_argument("--ollama-url", default=URL_PAR_DEFAUT)
    parseur.add_argument("--executions", type=int, default=3)
    args = parseur.parse_args()
    if not args.dossier.is_dir():
        print("dossier introuvable (pour le corpus Héron : uv run python exemples/generer.py)", file=sys.stderr)
        return 2
    try:
        reference = charger_dictionnaires([args.reference])
        client = ClientOllama(args.ollama_url, args.modele)
        client.verifier()
    except (ErreurConfiguration, ErreurOllama) as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 2
    docs = documents(args.dossier)
    texte = "\n".join(t for _, t in docs)
    print(f"{len(docs)} documents, modèle {args.modele}, {args.executions} exécutions")
    scores = []
    for n in range(1, args.executions + 1):
        chrono = Chronometre(client)
        try:
            bilan = analyser(docs, chrono, CATEGORIES_PAR_DEFAUT, Dictionnaire(), chrono.signaler)
        except ErreurOllama as e:
            print(f"erreur : {e}", file=sys.stderr)
            return 2
        score = comparer(bilan.candidats, reference, texte)
        scores.append(score)
        print(
            f"Exécution {n} : rappel {score.trouvees}/{score.reference} ({score.rappel:.0%}), "
            f"catégorie juste {score.bonne_categorie}/{score.trouvees}, "
            f"précision {score.justes}/{score.candidats} ({score.precision:.0%}), "
            f"morceaux non analysés {len(bilan.ignores)}"
        )
        print("  durées : " + " ; ".join(f"{nom} {chrono.durees[nom]:.0f} s" for nom, _ in docs))
    for libelle, valeurs in (("Rappel", [s.rappel for s in scores]), ("Précision", [s.precision for s in scores])):
        print(f"{libelle} : moyenne {statistics.mean(valeurs):.0%} (min {min(valeurs):.0%}, max {max(valeurs):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Vérifier que le script se charge et gère l'absence d'Ollama**

Run: `uv run python exemples/mesurer.py --ollama-url http://127.0.0.1:1 exemples`
Expected : `erreur : Ollama injoignable à http://127.0.0.1:1 (...) ; pour la stack locale, depuis local-llm/ : docker compose up -d ollama`, code 2. Le dossier `exemples` existe, la vérification d'Ollama est donc atteinte.

Run: `uv run pytest -q`
Expected: tous les tests passent.

- [ ] **Step 7: Commit**

```bash
git add src/obfuscation/detection/mesure.py exemples/mesurer.py tests/test_mesure.py
git commit -m "feat(obfuscation): mesure le rappel et la précision de la détection

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Documentation et exclusion git

**Files:**
- Modify: `README.md` (d'`obfuscation/`)
- Modify: `../CLAUDE.md` (racine du dépôt)
- Modify: `../.gitignore` (racine du dépôt)

- [ ] **Step 1: `.gitignore` racine**

Sous la ligne `*.table.json` du bloc « Obfuscation », ajouter :

```
*.candidats.yaml
```

Vérifier : `cd .. && touch obfuscation/essai.candidats.yaml && git status --short obfuscation/ && rm obfuscation/essai.candidats.yaml`
Expected : aucune ligne pour `essai.candidats.yaml`.

- [ ] **Step 2: README d'`obfuscation/`**

Insérer avant `## Dictionnaires` :

````markdown
## Détecter les termes avec un LLM local

Le dictionnaire ne masque que ce qu'il contient. `detecter` aide à le constituer : un LLM servi par Ollama lit les
documents bruts **en local** et propose les noms de clients, prestataires, projets, personnes et lieux qu'il repère.
Rien ne quitte la machine.

```bash
# Ollama doit tourner : celui de la stack local-llm (cd ../local-llm && docker compose up -d ollama),
# ou un Ollama natif (plus rapide sous macOS, où Docker n'a pas accès au GPU).
uv run detecter documents/ -o mon-client.candidats.yaml -d mon-client.yaml
# Relire mon-client.candidats.yaml : supprimer les lignes refusées, corriger les catégories. Puis :
uv run obfusquer documents/ -d mon-client.yaml -d mon-client.candidats.yaml -t ~/.obfuscation/mon-client.table.json -o sortie/
```

- Le résultat est un dictionnaire au format habituel, commenté (nombre d'occurrences, extrait de contexte) :

  ```yaml
  CLIENT:
    - [Acme Défense, Acme Defense, Acme]  # 14 occurrences ; variante présumée, à vérifier : Acme
      # « …le marché passé par Acme Défense pour… »
  ```

- Les termes des dictionnaires passés avec `-d` ne sont pas reproposés. Le fichier `-o` n'est jamais écrasé.
- Un terme que le modèle invente ou déforme est rejeté : seul ce qui figure dans le texte est proposé, sous la forme
  du texte. Un terme contenu dans un autre (`Acme` dans `Acme Défense`) est proposé comme variante présumée.
- Options : `--modele` (défaut `granite4.2:8b`), `--ollama-url` (défaut `http://127.0.0.1:11434`),
  `--categories` (défaut `CLIENT,PRESTATAIRE,PROJET,PERSONNE,LIEU`), `--delai` (secondes par appel, défaut 300).
- Codes de retour : `0` succès, `1` résultat incomplet (fichier illisible ou morceau non analysé, listé en tête du
  fichier), `2` erreur de configuration (Ollama injoignable, modèle absent, fichier `-o` existant).
- Les fichiers `*.candidats.yaml` contiennent des termes réels : ils sont exclus de git.

**Mesurer la détection** : `exemples/mesurer.py` compare le résultat à un dictionnaire validé (rappel : part des
termes retrouvés ; précision : part des propositions justes). Il n'affiche que des chiffres, jamais un terme ni un
nom de fichier.

```bash
uv run python exemples/generer.py && uv run python exemples/mesurer.py      # corpus fictif Héron
uv run python exemples/mesurer.py documents/ --reference mon-client.yaml    # documents réels
```

Le corpus Héron ne compte que quatre entités : la mesure y est indicative.
````

Dans `## Limites`, remplacer la ligne « Le dictionnaire ne trouve que ce qu'il contient : relire les documents obfusqués avant de les envoyer. » par :

```markdown
- Le dictionnaire ne trouve que ce qu'il contient, et `detecter` peut oublier des termes (surtout avec un petit
  modèle) : relire le candidat, puis les documents obfusqués avant de les envoyer.
```

Dans `## Développement`, remplacer la ligne « Conception : … » par :

```markdown
Conception : `docs/specs/2026-10-08-obfuscation-design.md`, `docs/specs/2026-10-08-detection-design.md` ;
plans : `docs/plans/2026-10-08-obfuscation.md`, `docs/plans/2026-10-08-detection.md`.
```

- [ ] **Step 3: `CLAUDE.md` racine**

Dans la ligne `obfuscation/`, remplacer `(`obfusquer` / `restaurer`).` par :

```markdown
(`obfusquer` / `restaurer`, et `detecter` qui propose un dictionnaire candidat à l'aide de l'Ollama de `local-llm/`).
```

Dans la règle « Ne jamais versionner… », ajouter `` les dictionnaires candidats `*.candidats.yaml`, `` après `` les tables de correspondance `*.table.json`, ``.

- [ ] **Step 4: Vérifier**

Run: `uv run pytest -q && git diff --stat`
Expected: tests verts ; seuls `README.md`, `CLAUDE.md` et `.gitignore` modifiés.

- [ ] **Step 5: Commit**

```bash
git add README.md ../CLAUDE.md ../.gitignore
git commit -m "docs(obfuscation): documente la commande detecter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Validation réelle sur le corpus Héron

Cette tâche nécessite Ollama. Elle porte uniquement sur le corpus fictif : ne jamais la lancer sur des documents réels.

- [ ] **Step 1: Démarrer Ollama seul**

Run: `cd ../local-llm && docker compose up -d ollama && curl -s http://127.0.0.1:11434/api/tags`
Expected : la liste contient `granite4.2:8b`. Sinon : `docker compose exec ollama ollama pull granite4.2:8b`.

- [ ] **Step 2: Lancer `detecter` sur le corpus**

Run (depuis `obfuscation/`) :

```bash
uv run python exemples/generer.py
uv run detecter exemples/generes -o /tmp/heron.candidats.yaml
cat /tmp/heron.candidats.yaml
uv run obfusquer exemples/generes -d /tmp/heron.candidats.yaml -t /tmp/heron.table.json -o /tmp/heron-sortie
```

Expected :
- `detecter` se termine avec le code 0 ;
- le YAML contient au moins `Novaltis`, `Acme Défense` et `Jeanne Martin` ;
- `obfusquer` l'accepte tel quel.

Noter les durées affichées.

- [ ] **Step 3: Mesurer**

Run: `uv run python exemples/mesurer.py`
Expected : 3 exécutions. Relever le rappel et la précision moyens, la variabilité et les durées par document.

- [ ] **Step 4: Rendre compte**

Résumer au formateur :
- le rappel et la précision mesurés ;
- les termes oubliés et les fausses alertes, ce qui est possible ici puisque le corpus est fictif ;
- les durées, en les attribuant à la configuration de référence ;
- les ajustements de prompt éventuels.

Tout changement de prompt fait l'objet d'un commit `fix(obfuscation): …` séparé, avec les tests à jour. Nettoyer : `rm -r /tmp/heron.candidats.yaml /tmp/heron.table.json /tmp/heron-sortie`. Laisser Ollama démarré ou l'arrêter selon le souhait du formateur (`docker compose stop ollama`).
