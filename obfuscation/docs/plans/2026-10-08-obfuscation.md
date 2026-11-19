# Outil d'obfuscation de documents — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Outil en ligne de commande `obfusquer` / `restaurer` qui remplace, de façon réversible, les termes sensibles de documents Word, Excel, PowerPoint, PDF et texte par des jetons `[CATEGORIE_n]` avant de les confier à Claude.

**Architecture:** Un moteur unique (`moteur.py`) calcule des remplacements `(debut, fin, texte)` à partir de dictionnaires YAML, de motifs regex et d'une table de correspondance locale ; il sert dans les deux sens. Les documents Office sont traités comme des archives zip de parties XML (lxml), sans python-docx/openpyxl/python-pptx à l'exécution ; les PDF sont convertis en Markdown. Un contrôle résiduel indépendant relit chaque fichier produit.

**Tech Stack:** Python 3.12, uv, lxml, PyYAML, pymupdf4llm (PyMuPDF) ; tests : pytest, python-docx, openpyxl, python-pptx.

**Spec:** `obfuscation/docs/specs/2026-10-08-obfuscation-design.md`

## Global Constraints

- Toutes les commandes se lancent depuis `obfuscation/` (`cd obfuscation`). Tests : `uv run pytest`.
- Python `>=3.12`. Dépendances d'exécution : `lxml>=6.1`, `pymupdf4llm>=1.28`, `pyyaml>=6.0.3`. Dépendances de développement (groupe `dev`) : `openpyxl>=3.1.5`, `pytest>=9.1`, `python-docx>=1.2`, `python-pptx>=1.0.2`.
- Code, identifiants, messages et documentation en français.
- Jetons : `[CATEGORIE_n]` ; catégories `^[A-Z][A-Z0-9_]*$` ; `motifs` est une clé réservée des dictionnaires.
- Codes de retour : 0 succès ; 1 au moins un fichier en erreur ou non conforme ; 2 erreur de configuration (dictionnaire, table, arguments).
- Fichier dont le contrôle résiduel trouve un terme : préfixe `NON-CONFORME_`.
- Aucun fichier binaire de test versionné : les documents de test sont fabriqués par `tests/documents.py`.
- Pas de chemin absolu propre à la machine dans le README. Ne jamais versionner `*.table.json`, `obfuscation/sortie/`, `obfuscation/restaure/`, `obfuscation/exemples/generes/`.
- Identifiants fictifs uniquement dans les tests et les exemples (SIREN `123 456 782`, SIRET `123 456 782 00010`, IBAN d'exemple `FR76 3000 6000 0112 3456 7890 189`).
- Commits : Conventional Commits, messages en français, terminés par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Ne commiter qu'avec l'accord du formateur donné au lancement de l'exécution ; sans cet accord, laisser les changements dans l'arbre de travail et proposer le découpage à la fin.

## Précisions apportées à la spec

Relevées en vérifiant les API (projet jetable) et reportées dans la spec :

1. **Chevauchements** : le plus long gagne, quelle que soit la source ; à longueur égale, le dictionnaire prime. Sinon `jeanne.martin@novaltis.example` deviendrait `jeanne.martin@[CLIENT_1].example` et le nom fuirait.
2. **Noms de feuilles Excel** : les crochets y sont interdits ; on y écrit le jeton nu (`CLIENT_1`), y compris dans les références de formules (`CLIENT_1!A1`). La restauration reconnaît déjà la forme nue.
3. **En-têtes Excel** : les codes `&C`, `&"Arial,Gras"`, `&12`… sont isolés avant remplacement (`&CNovaltis` ne serait pas un mot entier).
4. **Cellules numériques** : un nombre qui correspond entièrement à un motif (SIRET saisi comme nombre) devient une chaîne obfusquée.
5. **Passe générique** : outre les unités de texte (paragraphes, chaînes), tout élément XML portant du texte est traité (métadonnées, `w:instrText`, caches de graphiques…), sauf les valeurs numériques. Attributs traités : `author`, `initials`, `descr`, `title`, `tooltip`, `userName`, le `name` de `cNvPr`/`docPr`, le `displayName` de `person`, le `val` de `tblCaption`/`tblDescription`, et la cible des relations externes (liens `mailto:`/`https:`).
6. **PDF** : `pymupdf4llm.to_markdown(..., use_ocr=False)` ; sinon une OCR Tesseract est tentée si elle est installée.
7. **VML** : une partie `.vml` mal formée (fréquent dans Excel) est recopiée telle quelle ; le contrôle résiduel la vérifie en texte brut.
8. **Table** : sauvegardée (atomiquement, droits `0600`) après chaque fichier produit, pour qu'une interruption ne laisse pas de document impossible à restaurer.
9. **Modules** : les règles Word et PowerPoint tiennent dans une table commune (`formats/xml_texte.py`) ; seules les règles Excel ont leur module (`formats/excel.py`).

## Review Focus

- Interruption (Ctrl-C) au milieu d'un lot → la table contient déjà les jetons de chaque fichier écrit (test `test_interruption_table_deja_sauvegardee`, tâche 11).
- Dossier de sortie placé dans le dossier source, commande relancée → les sorties ne sont pas réobfusquées (test `test_sortie_dans_la_source_non_retraitee`, tâche 11).
- Terme dans une zone qu'aucune règle ne couvre (champ `HYPERLINK` dans `w:fldSimple/@w:instr`) → fichier `NON-CONFORME_` et code 1 (test `test_fuite_detectee_et_fichier_marque`, tâche 11).
- Fichiers produits par Office et non par les bibliothèques Python : chaînes partagées Excel en texte enrichi, VML mal formé (tests `test_chaines_partagees_texte_enrichi`, tâche 7, et `test_xlsx_vml_mal_forme_recopie`, tâche 9).
- Jetons reformatés par Claude en Markdown : `**[CLIENT_1]**`, `\[CLIENT_1\]`, `CLIENT_1,` (tests `test_restauration_tolerante`, tâche 4, et `test_restaurer_entree_standard`, tâche 11).

## Structure des fichiers

```
obfuscation/
├── pyproject.toml
├── README.md
├── src/obfuscation/
│   ├── __init__.py
│   ├── erreurs.py           # ErreurConfiguration, ErreurDictionnaire, ErreurTable, ErreurFichier
│   ├── table.py             # Table : jetons ↔ valeurs, sauvegarde atomique
│   ├── dictionnaire.py      # chargement YAML, validation, recherche des variantes
│   ├── motifs.py            # motifs intégrés, Luhn, IBAN
│   ├── moteur.py            # Remplacement, appliquer, Moteur
│   ├── segments.py          # reecrire : remplacements sur un texte découpé en segments
│   ├── controle.py          # Controle : recherche résiduelle dans un fichier produit
│   ├── cli.py               # main_obfusquer, main_restaurer
│   └── formats/
│       ├── __init__.py      # Resultat
│       ├── texte.py         # .md / .txt
│       ├── pdf.py           # PDF → Markdown
│       ├── excel.py         # formules, noms de feuilles, en-têtes, cellules numériques
│       ├── xml_texte.py     # unités de texte, passe générique, attributs
│       └── ooxml.py         # archive zip, récursion, miniature, avertissements
├── tests/
│   ├── conftest.py
│   ├── documents.py         # fabrique de documents de test
│   ├── test_table.py
│   ├── test_dictionnaire.py
│   ├── test_motifs.py
│   ├── test_moteur.py
│   ├── test_segments.py
│   ├── test_texte_pdf.py
│   ├── test_xml_texte.py
│   ├── test_ooxml.py
│   ├── test_controle.py
│   └── test_cli.py
├── exemples/
│   ├── dictionnaire.yaml
│   └── generer.py
└── docs/
    ├── specs/2026-10-08-obfuscation-design.md
    └── plans/2026-10-08-obfuscation.md
```

---

### Task 1: Squelette du projet et table de correspondance

**Files:**
- Create: `obfuscation/pyproject.toml`, `obfuscation/README.md`, `obfuscation/src/obfuscation/__init__.py`, `obfuscation/src/obfuscation/erreurs.py`, `obfuscation/src/obfuscation/table.py`
- Modify: `.gitignore` (racine du dépôt, en fin de fichier)
- Test: `obfuscation/tests/test_table.py`

**Interfaces:**
- Produces: `erreurs.ErreurConfiguration`, `ErreurDictionnaire(ErreurConfiguration)`, `ErreurTable(ErreurConfiguration)`, `ErreurFichier(Exception)` ; `table.Table(jetons: dict[str, str] | None = None)` avec `.jetons: dict[str, str]` (clé `"[CLIENT_1]"`), `.jeton_pour(categorie: str, valeur: str) -> str` (renvoie `"[CLIENT_1]"`), `.valeur(jeton_nu: str) -> str | None` (`"CLIENT_1"` → valeur), `Table.charger(chemin: Path) -> Table`, `.sauvegarder(chemin: Path) -> None`.

- [ ] **Step 1: Créer le projet**

`obfuscation/pyproject.toml` :

```toml
[project]
name = "obfuscation"
version = "0.1.0"
description = "Obfuscation réversible de documents Office et PDF avant de les confier à Claude"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "lxml>=6.1",
    "pymupdf4llm>=1.28",
    "pyyaml>=6.0.3",
]

[project.scripts]
obfusquer = "obfuscation.cli:main_obfusquer"
restaurer = "obfuscation.cli:main_restaurer"

[dependency-groups]
dev = [
    "openpyxl>=3.1.5",
    "pytest>=9.1",
    "python-docx>=1.2",
    "python-pptx>=1.0.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`obfuscation/README.md` (complété à la tâche 12) :

```markdown
# Obfuscation de documents

Remplace les termes sensibles de documents Word, Excel, PowerPoint, PDF et texte par des jetons `[CATEGORIE_n]`
avant de les confier à Claude, puis remet les termes réels dans les réponses.
```

`obfuscation/src/obfuscation/__init__.py` :

```python
"""Obfuscation réversible de documents avant de les confier à Claude."""
```

`obfuscation/src/obfuscation/erreurs.py` :

```python
"""Erreurs signalées à l'utilisateur."""


class ErreurConfiguration(Exception):
    """Dictionnaire, table ou arguments invalides : aucun fichier n'est traité."""


class ErreurDictionnaire(ErreurConfiguration):
    pass


class ErreurTable(ErreurConfiguration):
    pass


class ErreurFichier(Exception):
    """Un fichier ne peut pas être traité ; les autres le sont."""
```

Ajouter à la fin du `.gitignore` racine :

```gitignore

# Obfuscation — environnement, sorties et tables de correspondance (données sensibles)
obfuscation/.venv/
obfuscation/**/__pycache__/
obfuscation/.pytest_cache/
obfuscation/sortie/
obfuscation/restaure/
obfuscation/exemples/generes/
*.table.json
```

Run: `cd obfuscation && uv sync`
Expected: création de `.venv` et de `uv.lock`, installation sans erreur.

- [ ] **Step 2: Écrire les tests de la table**

`obfuscation/tests/test_table.py` :

```python
import json
import stat

import pytest

from obfuscation.erreurs import ErreurTable
from obfuscation.table import Table


def test_attribue_des_jetons_numerotes_par_categorie():
    table = Table()
    assert table.jeton_pour("CLIENT", "Novaltis") == "[CLIENT_1]"
    assert table.jeton_pour("CLIENT", "Acme") == "[CLIENT_2]"
    assert table.jeton_pour("PROJET", "Héron") == "[PROJET_1]"


def test_meme_valeur_meme_jeton_sans_tenir_compte_de_la_casse():
    table = Table()
    assert table.jeton_pour("EMAIL", "J.Martin@novaltis.fr") == table.jeton_pour("EMAIL", "j.martin@NOVALTIS.fr")
    assert table.valeur("EMAIL_1") == "J.Martin@novaltis.fr"
    assert table.valeur("EMAIL_2") is None


def test_sauvegarde_puis_rechargement_continue_la_numerotation(tmp_path):
    chemin = tmp_path / "client.table.json"
    table = Table()
    table.jeton_pour("CLIENT", "Novaltis")
    table.sauvegarder(chemin)
    assert json.loads(chemin.read_text(encoding="utf-8")) == {"version": 1, "jetons": {"[CLIENT_1]": "Novaltis"}}
    rechargee = Table.charger(chemin)
    assert rechargee.jeton_pour("CLIENT", "Novaltis") == "[CLIENT_1]"
    assert rechargee.jeton_pour("CLIENT", "Acme") == "[CLIENT_2]"


def test_table_absente_donne_une_table_vide(tmp_path):
    assert Table.charger(tmp_path / "absente.table.json").jetons == {}


def test_sauvegarde_atomique_lisible_par_le_seul_proprietaire(tmp_path):
    chemin = tmp_path / "t.table.json"
    Table().sauvegarder(chemin)
    assert stat.S_IMODE(chemin.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [chemin]


@pytest.mark.parametrize(
    "contenu",
    [
        "pas du json",
        '{"version": 2, "jetons": {}}',
        '{"version": 1, "jetons": {"CLIENT_1": "Novaltis"}}',
        '{"version": 1, "jetons": {"[CLIENT_1]": 3}}',
    ],
)
def test_table_invalide_refusee(tmp_path, contenu):
    chemin = tmp_path / "t.table.json"
    chemin.write_text(contenu, encoding="utf-8")
    with pytest.raises(ErreurTable):
        Table.charger(chemin)
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_table.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.table'`

- [ ] **Step 4: Implémenter la table**

`obfuscation/src/obfuscation/table.py` :

```python
"""Table de correspondance entre jetons et valeurs réelles. Elle ne doit jamais quitter la machine."""
import json
import os
import re
import tempfile
from pathlib import Path

from .erreurs import ErreurTable

VERSION = 1
FORME_JETON = re.compile(r"\[([A-Z][A-Z0-9_]*)_(\d+)\]")


class Table:
    def __init__(self, jetons: dict[str, str] | None = None):
        self.jetons: dict[str, str] = {}
        self._index: dict[tuple[str, str], str] = {}
        self._compteurs: dict[str, int] = {}
        for jeton, valeur in (jetons or {}).items():
            forme = FORME_JETON.fullmatch(jeton)
            if forme is None or not isinstance(valeur, str):
                raise ErreurTable(f"entrée invalide dans la table : {jeton!r}")
            self._enregistrer(jeton, forme.group(1), int(forme.group(2)), valeur)

    def _enregistrer(self, jeton: str, categorie: str, numero: int, valeur: str) -> None:
        self.jetons[jeton] = valeur
        self._index[(categorie, valeur.casefold())] = jeton
        self._compteurs[categorie] = max(self._compteurs.get(categorie, 0), numero)

    def jeton_pour(self, categorie: str, valeur: str) -> str:
        """Jeton de la valeur, créé au besoin ; une même valeur (casse ignorée) garde toujours le même jeton."""
        cle = (categorie, valeur.casefold())
        if cle not in self._index:
            numero = self._compteurs.get(categorie, 0) + 1
            self._enregistrer(f"[{categorie}_{numero}]", categorie, numero, valeur)
        return self._index[cle]

    def valeur(self, jeton_nu: str) -> str | None:
        return self.jetons.get(f"[{jeton_nu}]")

    @classmethod
    def charger(cls, chemin: Path) -> "Table":
        if not chemin.exists():
            return cls()
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ErreurTable(f"{chemin} : table illisible ({e})") from e
        if not isinstance(donnees, dict) or donnees.get("version") != VERSION or not isinstance(donnees.get("jetons"), dict):
            raise ErreurTable(f"{chemin} : format de table inconnu")
        try:
            return cls(donnees["jetons"])
        except ErreurTable as e:
            raise ErreurTable(f"{chemin} : {e}") from e

    def sauvegarder(self, chemin: Path) -> None:
        """Écriture atomique ; le fichier temporaire de mkstemp a les droits 0600, conservés par le renommage."""
        chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = json.dumps({"version": VERSION, "jetons": self.jetons}, ensure_ascii=False, indent=2) + "\n"
        descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, prefix=f".{chemin.name}.", suffix=".tmp")
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
                fichier.write(contenu)
            os.replace(temporaire, chemin)
        except BaseException:
            Path(temporaire).unlink(missing_ok=True)
            raise
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_table.py -v`
Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add .gitignore obfuscation/pyproject.toml obfuscation/uv.lock obfuscation/README.md obfuscation/src obfuscation/tests/test_table.py obfuscation/docs
git commit -m "feat(obfuscation): crée le projet et la table de correspondance"
```

(La spec et le plan, dans `obfuscation/docs`, partent avec ce premier commit.)

---

### Task 2: Dictionnaires

**Files:**
- Create: `obfuscation/src/obfuscation/dictionnaire.py`
- Test: `obfuscation/tests/test_dictionnaire.py`

**Interfaces:**
- Consumes: `erreurs.ErreurDictionnaire`.
- Produces: `normaliser(texte: str) -> str` ; `motif_de_terme(terme: str) -> str` (regex d'un terme, espaces quelconques entre mots) ; `Terme(categorie: str, canonique: str)` (dataclass figée) ; `Dictionnaire` avec `.termes: dict[str, Terme]`, `.variantes: list[str]`, `.motifs: dict[str, re.Pattern]`, `.terme(trouve: str) -> Terme | None`, `.recherche: re.Pattern | None` (groupe 1 = variante trouvée, correspondances chevauchantes) ; `charger_dictionnaires(chemins: list[Path]) -> Dictionnaire`.

- [ ] **Step 1: Écrire les tests**

`obfuscation/tests/test_dictionnaire.py` :

```python
import textwrap

import pytest

from obfuscation.dictionnaire import Terme, charger_dictionnaires
from obfuscation.erreurs import ErreurDictionnaire


def ecrire(tmp_path, contenu, nom="dico.yaml"):
    chemin = tmp_path / nom
    chemin.write_text(textwrap.dedent(contenu), encoding="utf-8")
    return chemin


def test_variantes_associees_a_la_forme_canonique(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, """
        CLIENT:
          - [Novaltis, Novaltis SA, NVL]
          - Acme
        """)])
    assert dictionnaire.terme("nvl") == Terme("CLIENT", "Novaltis")
    assert dictionnaire.terme("NOVALTIS  sa") == Terme("CLIENT", "Novaltis")
    assert dictionnaire.terme("ACME") == Terme("CLIENT", "Acme")
    assert dictionnaire.terme("Inconnu") is None


def test_recherche_mots_entiers_casse_et_espaces_insecables(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, """
        PROJET:
          - [Projet Héron, Héron]
        """)])
    texte = "Le projet\u00a0héron, les Hérons et HÉRON."
    trouves = [m.group(1) for m in dictionnaire.recherche.finditer(texte)]
    assert trouves == ["projet\u00a0héron", "héron", "HÉRON"]


def test_plusieurs_dictionnaires_fusionnes(tmp_path):
    dictionnaire = charger_dictionnaires([
        ecrire(tmp_path, "CLIENT:\n  - Novaltis\n", "a.yaml"),
        ecrire(tmp_path, "PROJET:\n  - Héron\n", "b.yaml"),
    ])
    assert dictionnaire.terme("novaltis").categorie == "CLIENT"
    assert dictionnaire.terme("héron").categorie == "PROJET"


def test_meme_terme_dans_deux_categories_refuse_avec_positions(tmp_path):
    a = ecrire(tmp_path, "CLIENT:\n  - Héron\n", "a.yaml")
    b = ecrire(tmp_path, "PROJET:\n  - Projet X\n  - héron\n", "b.yaml")
    with pytest.raises(ErreurDictionnaire) as erreur:
        charger_dictionnaires([a, b])
    message = str(erreur.value)
    assert f"{b}:3" in message and "CLIENT" in message and f"{a}:2" in message


def test_motifs_personnalises(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, r"""
        motifs:
          CONTRAT: 'CTR-\d{6}'
        """)])
    assert dictionnaire.motifs["CONTRAT"].fullmatch("CTR-123456")
    assert dictionnaire.recherche is None


def test_dictionnaire_vide(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, "")])
    assert dictionnaire.termes == {} and dictionnaire.recherche is None


@pytest.mark.parametrize(
    "contenu, attendu",
    [
        ("client:\n  - x\n", "dico.yaml:1"),
        ("CLIENT: Novaltis\n", "dico.yaml:1"),
        ("CLIENT:\n  - [Novaltis, '']\n", "dico.yaml:2"),
        ("motifs:\n  CONTRAT: 'CTR-(\\d'\n", "dico.yaml:2"),
        ("CLIENT: [\n", "YAML invalide"),
        ("- Novaltis\n", "dico.yaml:1"),
    ],
)
def test_erreurs_signalees_avec_position(tmp_path, contenu, attendu):
    with pytest.raises(ErreurDictionnaire, match=attendu.replace(".", r"\.")):
        charger_dictionnaires([ecrire(tmp_path, contenu)])
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_dictionnaire.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.dictionnaire'`

- [ ] **Step 3: Implémenter**

`obfuscation/src/obfuscation/dictionnaire.py` :

```python
"""Dictionnaires YAML : catégories de termes sensibles et motifs propres au contexte."""
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

from .erreurs import ErreurDictionnaire

CATEGORIE = re.compile(r"[A-Z][A-Z0-9_]*")
CLE_MOTIFS = "motifs"


def normaliser(texte: str) -> str:
    """Forme de comparaison : espaces réduites, casse ignorée."""
    return " ".join(texte.split()).casefold()


def motif_de_terme(terme: str) -> str:
    """Regex d'un terme : toute suite d'espaces (insécables comprises) est acceptée entre ses mots."""
    return r"\s+".join(re.escape(mot) for mot in terme.split())


@dataclass(frozen=True)
class Terme:
    categorie: str
    canonique: str


@dataclass
class Dictionnaire:
    termes: dict[str, Terme] = field(default_factory=dict)  # clé : variante normalisée
    variantes: list[str] = field(default_factory=list)  # telles qu'écrites dans le YAML
    motifs: dict[str, re.Pattern] = field(default_factory=dict)

    def terme(self, trouve: str) -> Terme | None:
        return self.termes.get(normaliser(trouve))

    @cached_property
    def recherche(self) -> re.Pattern | None:
        """À chaque position, la plus longue variante qui y commence ; le groupe 1 est la variante trouvée.

        Le lookahead rend les correspondances chevauchantes : le moteur choisit ensuite la plus longue.
        """
        if not self.variantes:
            return None
        alternatives = "|".join(motif_de_terme(v) for v in sorted(self.variantes, key=len, reverse=True))
        return re.compile(rf"(?=(?<!\w)({alternatives})(?!\w))", re.IGNORECASE)


def charger_dictionnaires(chemins: list[Path]) -> Dictionnaire:
    dictionnaire = Dictionnaire()
    origines: dict[str, str] = {}  # variante normalisée → « fichier:ligne » de sa déclaration
    for chemin in chemins:
        _charger(chemin, dictionnaire, origines)
    return dictionnaire


def _position(chemin: Path, noeud: yaml.Node) -> str:
    return f"{chemin}:{noeud.start_mark.line + 1}"


def _charger(chemin: Path, dictionnaire: Dictionnaire, origines: dict[str, str]) -> None:
    try:
        racine = yaml.compose(chemin.read_text(encoding="utf-8"))
    except OSError as e:
        raise ErreurDictionnaire(f"{chemin} : lecture impossible ({e.strerror})") from e
    except (UnicodeDecodeError, yaml.YAMLError) as e:
        raise ErreurDictionnaire(f"{chemin} : YAML invalide\n{e}") from e
    if racine is None:
        return
    if not isinstance(racine, yaml.MappingNode):
        raise ErreurDictionnaire(f"{_position(chemin, racine)} : le dictionnaire doit associer des catégories à des listes de termes")
    for cle, valeur in racine.value:
        if isinstance(cle, yaml.ScalarNode) and cle.value == CLE_MOTIFS:
            _charger_motifs(chemin, valeur, dictionnaire)
        else:
            _charger_categorie(chemin, cle, valeur, dictionnaire, origines)


def _nom_categorie(chemin: Path, cle: yaml.Node) -> str:
    if not isinstance(cle, yaml.ScalarNode) or not CATEGORIE.fullmatch(cle.value):
        raise ErreurDictionnaire(
            f"{_position(chemin, cle)} : catégorie invalide {cle.value!r} "
            "(majuscules, chiffres et _, en commençant par une lettre)"
        )
    return cle.value


def _charger_categorie(chemin, cle, valeur, dictionnaire: Dictionnaire, origines: dict[str, str]) -> None:
    categorie = _nom_categorie(chemin, cle)
    if not isinstance(valeur, yaml.SequenceNode):
        raise ErreurDictionnaire(f"{_position(chemin, valeur)} : la catégorie {categorie} doit contenir une liste")
    for entree in valeur.value:
        variantes = entree.value if isinstance(entree, yaml.SequenceNode) else [entree]
        if not variantes or not all(isinstance(v, yaml.ScalarNode) and v.value.strip() for v in variantes):
            raise ErreurDictionnaire(
                f"{_position(chemin, entree)} : entrée invalide (un terme, ou une liste de variantes non vides)"
            )
        canonique = " ".join(variantes[0].value.split())
        for noeud in variantes:
            cle_terme = normaliser(noeud.value)
            existant = dictionnaire.termes.get(cle_terme)
            if existant is not None:
                if existant.categorie != categorie:
                    raise ErreurDictionnaire(
                        f"{_position(chemin, noeud)} : « {noeud.value} » figure déjà dans la catégorie "
                        f"{existant.categorie} ({origines[cle_terme]})"
                    )
                continue  # doublon dans la même catégorie : la première déclaration fait foi
            dictionnaire.termes[cle_terme] = Terme(categorie, canonique)
            dictionnaire.variantes.append(noeud.value.strip())
            origines[cle_terme] = _position(chemin, noeud)


def _charger_motifs(chemin: Path, noeud: yaml.Node, dictionnaire: Dictionnaire) -> None:
    if not isinstance(noeud, yaml.MappingNode):
        raise ErreurDictionnaire(f"{_position(chemin, noeud)} : « motifs » doit associer des catégories à des expressions régulières")
    for cle, valeur in noeud.value:
        categorie = _nom_categorie(chemin, cle)
        if not isinstance(valeur, yaml.ScalarNode):
            raise ErreurDictionnaire(f"{_position(chemin, valeur)} : le motif {categorie} doit être une chaîne")
        try:
            dictionnaire.motifs[categorie] = re.compile(valeur.value)
        except re.error as e:
            raise ErreurDictionnaire(
                f"{_position(chemin, valeur)} : expression régulière invalide pour {categorie} ({e})"
            ) from e
```

- [ ] **Step 4: Vérifier le succès**

Run: `uv run pytest tests/test_dictionnaire.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add obfuscation/src/obfuscation/dictionnaire.py obfuscation/tests/test_dictionnaire.py
git commit -m "feat(obfuscation): charge et valide les dictionnaires YAML"
```

---

### Task 3: Motifs intégrés

**Files:**
- Create: `obfuscation/src/obfuscation/motifs.py`
- Test: `obfuscation/tests/test_motifs.py`

**Interfaces:**
- Produces: `Motif(categorie: str, regex: re.Pattern, valide: Callable[[str], bool])` (dataclass figée, `valide` par défaut toujours vrai) ; `MOTIFS_INTEGRES: tuple[Motif, ...]` (catégories `EMAIL`, `URL`, `IBAN`, `SIRET`, `SIREN`, `TELEPHONE`, `IP`) ; `luhn(chiffres: str) -> bool` ; `iban_valide(texte: str) -> bool`.

- [ ] **Step 1: Écrire les tests**

`obfuscation/tests/test_motifs.py` :

```python
import pytest

from obfuscation.motifs import MOTIFS_INTEGRES, iban_valide, luhn


def trouver(categorie, texte):
    motif = next(m for m in MOTIFS_INTEGRES if m.categorie == categorie)
    return [m.group() for m in motif.regex.finditer(texte) if motif.valide(m.group())]


@pytest.mark.parametrize(
    "categorie, texte, attendu",
    [
        ("EMAIL", "Écrire à jeanne.martin@novaltis.example.", ["jeanne.martin@novaltis.example"]),
        ("EMAIL", "pas une adresse : novaltis@", []),
        (
            "URL",
            "Voir https://intranet.novaltis.fr/offres?id=3. Et (https://a.b/c)",
            ["https://intranet.novaltis.fr/offres?id=3", "https://a.b/c"],
        ),
        (
            "IBAN",
            "IBAN FR76 3000 6000 0112 3456 7890 189 ou FR7630006000011234567890189.",
            ["FR76 3000 6000 0112 3456 7890 189", "FR7630006000011234567890189"],
        ),
        ("IBAN", "clé fausse FR76 3000 6000 0112 3456 7890 188", []),
        ("SIRET", "SIRET 123 456 782 00010 et 12345678200010", ["123 456 782 00010", "12345678200010"]),
        ("SIRET", "commande 12345678901234", []),
        ("SIREN", "SIREN 123 456 782, mais pas dans 123 456 782 00010", ["123 456 782"]),
        ("SIREN", "référence 123456789", []),
        (
            "TELEPHONE",
            "01 23 45 67 89, 06.12.34.56.78, +33 6 12 34 56 78, +33 (0)1 23 45 67 89, +44 20 7946 0958",
            ["01 23 45 67 89", "06.12.34.56.78", "+33 6 12 34 56 78", "+33 (0)1 23 45 67 89", "+44 20 7946 0958"],
        ),
        ("TELEPHONE", "montant 1234567, année 2026", []),
        ("IP", "serveur 10.0.12.5, version 1.2.3.4.5, 256.1.1.1, fin 192.168.1.1.", ["10.0.12.5", "192.168.1.1"]),
    ],
)
def test_motifs(categorie, texte, attendu):
    assert trouver(categorie, texte) == attendu


def test_cles_de_controle():
    assert luhn("123456782") and not luhn("123456789")
    assert iban_valide("FR76 3000 6000 0112 3456 7890 189")
    assert not iban_valide("FR76 3000 6000 0112 3456 7890 188")
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_motifs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.motifs'`

- [ ] **Step 3: Implémenter**

`obfuscation/src/obfuscation/motifs.py` :

```python
"""Motifs intégrés : valeurs reconnaissables sans dictionnaire (e-mail, téléphone, IBAN…)."""
import re
from collections.abc import Callable
from dataclasses import dataclass


def _toujours(_texte: str) -> bool:
    return True


@dataclass(frozen=True)
class Motif:
    categorie: str
    regex: re.Pattern
    valide: Callable[[str], bool] = _toujours


def luhn(chiffres: str) -> bool:
    """Clé de contrôle des SIREN et SIRET."""
    total = 0
    for rang, chiffre in enumerate(reversed(chiffres)):
        n = int(chiffre)
        if rang % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _luhn_sans_espaces(texte: str) -> bool:
    return luhn(texte.replace(" ", ""))


def iban_valide(texte: str) -> bool:
    """Clé modulo 97 : les quatre premiers caractères passent à la fin, les lettres deviennent 10 à 35."""
    compact = texte.replace(" ", "").upper()
    reordonne = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in reordonne)) % 97 == 1


OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"

MOTIFS_INTEGRES: tuple[Motif, ...] = (
    Motif("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # La ponctuation finale (point de fin de phrase, parenthèse fermante) ne fait pas partie de l'URL.
    Motif("URL", re.compile(r"https?://[^\s<>\"'\])]*[^\s<>\"'\]).,;:!?]", re.IGNORECASE)),
    Motif(
        "IBAN",
        re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?(?![A-Z0-9])"),
        iban_valide,
    ),
    Motif("SIRET", re.compile(r"(?<!\d)(?<!\d )\d{3} ?\d{3} ?\d{3} ?\d{5}(?! ?\d)"), _luhn_sans_espaces),
    Motif("SIREN", re.compile(r"(?<!\d)(?<!\d )\d{3} ?\d{3} ?\d{3}(?! ?\d)"), _luhn_sans_espaces),
    Motif(
        "TELEPHONE",
        re.compile(
            r"(?<![\w+])(?:(?:\+33 ?(?:\(0\) ?)?|0)[1-9](?:[ .-]?\d{2}){4}"
            r"|\+(?!33)[1-9]\d{0,2}(?:[ .-]?\d){6,12})(?!\d)"
        ),
    ),
    Motif("IP", re.compile(rf"(?<![\d.])(?:{OCTET}\.){{3}}{OCTET}(?!\d|\.\d)")),
)
```

- [ ] **Step 4: Vérifier le succès**

Run: `uv run pytest tests/test_motifs.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add obfuscation/src/obfuscation/motifs.py obfuscation/tests/test_motifs.py
git commit -m "feat(obfuscation): ajoute les motifs intégrés (e-mail, téléphone, IBAN, SIRET…)"
```

---

### Task 4: Moteur de remplacement

**Files:**
- Create: `obfuscation/src/obfuscation/moteur.py`, `obfuscation/tests/conftest.py`, `obfuscation/tests/documents.py` (constante `DICO` seulement ; complété à la tâche 9)
- Test: `obfuscation/tests/test_moteur.py`

**Interfaces:**
- Consumes: `Dictionnaire`, `Terme`, `charger_dictionnaires` (tâche 2) ; `MOTIFS_INTEGRES`, `Motif` (tâche 3) ; `Table` (tâche 1).
- Produces: `Sens = Literal["obfusquer", "restaurer"]` ; `Remplacement(debut: int, fin: int, texte: str, jeton: str)` (dataclass figée ; `jeton` est nu, ex. `"CLIENT_1"`) ; `appliquer(texte: str, remplacements: list[Remplacement]) -> str` ; `Moteur(dictionnaire, table)` avec `.dictionnaire`, `.table`, `.inconnus: set[str]`, `.avertissements: list[str]`, `.remplacements(texte, sens) -> list[Remplacement]` (triés, sans chevauchement), `.transformer(texte, sens) -> str`. Fixtures pytest `dictionnaire` et `moteur`.

- [ ] **Step 1: Fixtures communes**

`obfuscation/tests/documents.py` :

```python
"""Fabrique des documents de test : aucun binaire n'est versionné."""

DICO = r"""
CLIENT:
  - [Novaltis, Novaltis SA, Novaltis S.A., NVL]
PROJET:
  - [Projet Héron, Héron, Heron]
PERSONNE:
  - [Jeanne Martin, J. Martin]
motifs:
  CONTRAT: 'CTR-\d{6}'
"""
```

`obfuscation/tests/conftest.py` :

```python
import pytest
from documents import DICO

from obfuscation.dictionnaire import charger_dictionnaires
from obfuscation.moteur import Moteur
from obfuscation.table import Table


@pytest.fixture
def dictionnaire(tmp_path):
    chemin = tmp_path / "dico.yaml"
    chemin.write_text(DICO, encoding="utf-8")
    return charger_dictionnaires([chemin])


@pytest.fixture
def moteur(dictionnaire):
    return Moteur(dictionnaire, Table())
```

- [ ] **Step 2: Écrire les tests**

`obfuscation/tests/test_moteur.py` :

```python
def test_obfusque_termes_et_motifs(moteur):
    texte = "Novaltis SA (NVL) pilote le Projet Héron ; contact : jeanne.martin@novaltis.example, contrat CTR-123456."
    assert moteur.transformer(texte, "obfusquer") == (
        "[CLIENT_1] ([CLIENT_1]) pilote le [PROJET_1] ; contact : [EMAIL_1], contrat [CONTRAT_1]."
    )


def test_le_plus_long_gagne_meme_contre_le_dictionnaire(moteur):
    # « novaltis » est dans le dictionnaire, mais l'adresse est plus longue : rien ne doit fuiter d'elle.
    assert moteur.transformer("j.martin@novaltis.example", "obfusquer") == "[EMAIL_1]"


def test_mots_entiers_seulement(moteur):
    assert moteur.transformer("Les Hérons de NVLX", "obfusquer") == "Les Hérons de NVLX"


def test_terme_finissant_par_un_point(moteur):
    assert moteur.transformer("Novaltis S.A. signe.", "obfusquer") == "[CLIENT_1] signe."


def test_table_partagee_entre_textes(moteur):
    moteur.transformer("Novaltis", "obfusquer")
    assert moteur.transformer("Héron et NVL", "obfusquer") == "[PROJET_1] et [CLIENT_1]"


def test_aller_retour_exact(moteur):
    texte = "Le Projet Héron de Novaltis : Jeanne Martin, 06 12 34 56 78."
    obfusque = moteur.transformer(texte, "obfusquer")
    assert "Novaltis" not in obfusque and "06 12" not in obfusque
    assert moteur.transformer(obfusque, "restaurer") == texte


def test_restauration_tolerante(moteur):
    moteur.transformer("Novaltis", "obfusquer")
    texte = "[CLIENT_1], **[CLIENT_1]**, \\[CLIENT_1\\], CLIENT_1, xCLIENT_1 et CLIENT_12"
    assert moteur.transformer(texte, "restaurer") == "Novaltis, **Novaltis**, Novaltis, Novaltis, xCLIENT_1 et CLIENT_12"
    assert moteur.inconnus == set()


def test_jetons_inconnus_signales(moteur):
    assert moteur.transformer("[CLIENT_9]", "restaurer") == "[CLIENT_9]"
    assert moteur.inconnus == {"[CLIENT_9]"}
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_moteur.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.moteur'`

- [ ] **Step 4: Implémenter**

`obfuscation/src/obfuscation/moteur.py` :

```python
"""Moteur de remplacement, commun à tous les formats et aux deux sens."""
import re
from dataclasses import dataclass
from typing import Literal

from .dictionnaire import Dictionnaire
from .motifs import MOTIFS_INTEGRES, Motif
from .table import Table

Sens = Literal["obfusquer", "restaurer"]
JETON_ENTRE_CROCHETS = re.compile(r"\\?\[([A-Z][A-Z0-9_]*_\d+)\\?\]")


@dataclass(frozen=True)
class Remplacement:
    debut: int
    fin: int
    texte: str  # ce qui remplace texte[debut:fin]
    jeton: str  # jeton nu, sans crochets : « CLIENT_1 »


def appliquer(texte: str, remplacements: list[Remplacement]) -> str:
    morceaux, curseur = [], 0
    for r in remplacements:
        morceaux += [texte[curseur:r.debut], r.texte]
        curseur = r.fin
    morceaux.append(texte[curseur:])
    return "".join(morceaux)


class Moteur:
    def __init__(self, dictionnaire: Dictionnaire, table: Table):
        self.dictionnaire = dictionnaire
        self.table = table
        self.motifs = [*MOTIFS_INTEGRES, *(Motif(c, r) for c, r in dictionnaire.motifs.items())]
        self.inconnus: set[str] = set()  # jetons rencontrés à la restauration mais absents de la table
        self.avertissements: list[str] = []
        self._jetons_connus: re.Pattern | None = None
        self._taille_table = -1

    def remplacements(self, texte: str, sens: Sens) -> list[Remplacement]:
        if sens == "obfusquer":
            return self._a_obfusquer(texte)
        return self._a_restaurer(texte)

    def transformer(self, texte: str, sens: Sens) -> str:
        return appliquer(texte, self.remplacements(texte, sens))

    def _a_obfusquer(self, texte: str) -> list[Remplacement]:
        candidats = []  # (debut, fin, priorité : 0 dictionnaire / 1 motif, catégorie, valeur pour la table)
        if self.dictionnaire.recherche is not None:
            for m in self.dictionnaire.recherche.finditer(texte):
                terme = self.dictionnaire.terme(m.group(1))
                if terme is not None:
                    candidats.append((m.start(1), m.end(1), 0, terme.categorie, terme.canonique))
        for motif in self.motifs:
            for m in motif.regex.finditer(texte):
                if m.end() > m.start() and motif.valide(m.group()):
                    candidats.append((m.start(), m.end(), 1, motif.categorie, m.group()))
        # Le plus long gagne ; à longueur égale, le dictionnaire prime, puis le plus à gauche.
        candidats.sort(key=lambda c: (c[0] - c[1], c[2], c[0]))
        retenus: list[Remplacement] = []
        for debut, fin, _, categorie, valeur in candidats:
            if any(debut < r.fin and r.debut < fin for r in retenus):
                continue
            jeton = self.table.jeton_pour(categorie, valeur)
            retenus.append(Remplacement(debut, fin, jeton, jeton[1:-1]))
        return sorted(retenus, key=lambda r: r.debut)

    def _a_restaurer(self, texte: str) -> list[Remplacement]:
        for m in JETON_ENTRE_CROCHETS.finditer(texte):
            if self.table.valeur(m.group(1)) is None:
                self.inconnus.add(m.group(0))
        recherche = self._recherche_jetons()
        if recherche is None:
            return []
        return [
            Remplacement(m.start(), m.end(), self.table.valeur(m.group(1)), m.group(1))
            for m in recherche.finditer(texte)
        ]

    def _recherche_jetons(self) -> re.Pattern | None:
        """Jetons connus, avec ou sans crochets, crochets échappés en Markdown compris."""
        if self._taille_table != len(self.table.jetons):
            nus = sorted((jeton[1:-1] for jeton in self.table.jetons), key=len, reverse=True)
            self._jetons_connus = (
                re.compile(r"(?:\\?\[)?(?<!\w)(" + "|".join(map(re.escape, nus)) + r")(?!\w)(?:\\?\])?")
                if nus
                else None
            )
            self._taille_table = len(self.table.jetons)
        return self._jetons_connus
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_moteur.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add obfuscation/src/obfuscation/moteur.py obfuscation/tests/conftest.py obfuscation/tests/documents.py obfuscation/tests/test_moteur.py
git commit -m "feat(obfuscation): ajoute le moteur de remplacement réversible"
```

---

### Task 5: Segments (paragraphes découpés en morceaux de mise en forme)

**Files:**
- Create: `obfuscation/src/obfuscation/segments.py`
- Test: `obfuscation/tests/test_segments.py`

**Interfaces:**
- Consumes: `Remplacement` (tâche 4).
- Produces: `reecrire(textes: list[str], remplacements: list[Remplacement]) -> list[str]` (même longueur que `textes` ; positions des remplacements relatives à `"".join(textes)`).

- [ ] **Step 1: Écrire les tests**

`obfuscation/tests/test_segments.py` :

```python
from obfuscation.moteur import Remplacement
from obfuscation.segments import reecrire


def r(debut, fin, texte):
    return Remplacement(debut, fin, texte, "X_1")


def test_terme_coupe_sur_deux_segments():
    assert reecrire(["Nova", "ltis signe."], [r(0, 8, "[CLIENT_1]")]) == ["[CLIENT_1]", " signe."]


def test_terme_sur_plusieurs_segments_avec_segment_vide():
    textes = ["Le Pro", "", "jet Hé", "ron."]
    assert reecrire(textes, [r(3, 15, "[PROJET_1]")]) == ["Le [PROJET_1]", "", "", "."]


def test_plusieurs_remplacements():
    assert reecrire(["Novaltis et ", "Héron"], [r(0, 8, "[C_1]"), r(12, 17, "[P_1]")]) == ["[C_1] et ", "[P_1]"]


def test_sans_remplacement():
    assert reecrire(["a", "b"], []) == ["a", "b"]
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_segments.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.segments'`

- [ ] **Step 3: Implémenter**

`obfuscation/src/obfuscation/segments.py` :

```python
"""Remplacements dans un texte découpé en segments (les morceaux de mise en forme d'un paragraphe Office)."""
from .moteur import Remplacement


def reecrire(textes: list[str], remplacements: list[Remplacement]) -> list[str]:
    """Nouveau texte de chaque segment.

    Le remplaçant va dans le segment où commence la correspondance, dont il prend la mise en forme ;
    la suite de la correspondance est retirée des segments suivants.
    """
    complet = "".join(textes)
    resultat, debut = [], 0
    for texte in textes:
        fin = debut + len(texte)
        morceaux, curseur = [], debut
        for r in remplacements:
            if r.fin <= curseur or r.debut >= fin:
                continue
            if r.debut >= debut:
                morceaux += [complet[curseur:r.debut], r.texte]
            curseur = min(r.fin, fin)
        morceaux.append(complet[curseur:fin])
        resultat.append("".join(morceaux))
        debut = fin
    return resultat
```

- [ ] **Step 4: Vérifier le succès**

Run: `uv run pytest tests/test_segments.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add obfuscation/src/obfuscation/segments.py obfuscation/tests/test_segments.py
git commit -m "feat(obfuscation): remplace les termes coupés entre plusieurs segments"
```

---

### Task 6: Formats texte et PDF

**Files:**
- Create: `obfuscation/src/obfuscation/formats/__init__.py`, `obfuscation/src/obfuscation/formats/texte.py`, `obfuscation/src/obfuscation/formats/pdf.py`
- Modify: `obfuscation/tests/documents.py` (ajout de `pdf_exemple`)
- Test: `obfuscation/tests/test_texte_pdf.py`

**Interfaces:**
- Consumes: `Moteur`, `Sens` (tâche 4), `ErreurFichier` (tâche 1).
- Produces: `formats.Resultat(donnees: bytes, avertissements: list[str] = [])` ; `formats.texte.transformer_texte(donnees: bytes, moteur, sens, nom="texte") -> Resultat` ; `formats.pdf.pdf_vers_markdown(donnees: bytes, nom="document.pdf") -> str` ; `documents.pdf_exemple(html: str | None = None) -> bytes`.

- [ ] **Step 1: Fabrique de PDF de test**

Ajouter à `obfuscation/tests/documents.py` (après la docstring, avant `DICO`) :

```python
import pymupdf


def pdf_exemple(html: str | None = None) -> bytes:
    """PDF d'une page ; sans HTML, la page est vide (comme un scan sans couche texte)."""
    document = pymupdf.open()
    page = document.new_page()
    if html:
        page.insert_htmlbox(pymupdf.Rect(50, 50, 550, 800), html)
    return document.tobytes()
```

- [ ] **Step 2: Écrire les tests**

`obfuscation/tests/test_texte_pdf.py` :

```python
import pytest
from documents import pdf_exemple

from obfuscation.erreurs import ErreurFichier
from obfuscation.formats.pdf import pdf_vers_markdown
from obfuscation.formats.texte import transformer_texte


def test_texte_aller_retour_fins_de_ligne_conservees(moteur):
    original = "Le Projet Héron\r\nNovaltis\r\n".encode("utf-8")
    obfusque = transformer_texte(original, moteur, "obfusquer").donnees
    assert obfusque == "Le [PROJET_1]\r\n[CLIENT_1]\r\n".encode("utf-8")
    assert transformer_texte(obfusque, moteur, "restaurer").donnees == original


def test_texte_avec_bom(moteur):
    assert transformer_texte("\ufeffNVL".encode("utf-8"), moteur, "obfusquer").donnees == b"[CLIENT_1]"


def test_texte_non_utf8_refuse(moteur):
    with pytest.raises(ErreurFichier, match="UTF-8"):
        transformer_texte("Héron".encode("latin-1"), moteur, "obfusquer", "note.txt")


def test_pdf_vers_markdown():
    markdown = pdf_vers_markdown(pdf_exemple("<h1>Projet Héron</h1><p>Contact : jeanne.martin@novaltis.example</p>"))
    assert "Projet Héron" in markdown and "jeanne.martin@novaltis.example" in markdown


def test_pdf_sans_texte_refuse():
    with pytest.raises(ErreurFichier, match="OCR"):
        pdf_vers_markdown(pdf_exemple(), "scan.pdf")


def test_pdf_corrompu_refuse():
    with pytest.raises(ErreurFichier, match="PDF illisible"):
        pdf_vers_markdown(b"pas un pdf", "casse.pdf")
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_texte_pdf.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.formats'`

- [ ] **Step 4: Implémenter**

`obfuscation/src/obfuscation/formats/__init__.py` :

```python
"""Adaptateurs de formats : chacun applique le moteur au texte d'un type de fichier."""
from dataclasses import dataclass, field


@dataclass
class Resultat:
    donnees: bytes
    avertissements: list[str] = field(default_factory=list)
```

`obfuscation/src/obfuscation/formats/texte.py` :

```python
"""Fichiers texte (.md, .txt) : UTF-8, fins de ligne conservées."""
from ..erreurs import ErreurFichier
from ..moteur import Moteur, Sens
from . import Resultat


def transformer_texte(donnees: bytes, moteur: Moteur, sens: Sens, nom: str = "texte") -> Resultat:
    try:
        texte = donnees.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ErreurFichier(f"{nom} : texte non encodé en UTF-8") from e
    return Resultat(moteur.transformer(texte, sens).encode("utf-8"))
```

`obfuscation/src/obfuscation/formats/pdf.py` :

```python
"""PDF → Markdown : la mise en page est perdue, le texte est conservé. PyMuPDF est sous licence AGPL."""
import pymupdf
import pymupdf4llm

from ..erreurs import ErreurFichier


def pdf_vers_markdown(donnees: bytes, nom: str = "document.pdf") -> str:
    try:
        document = pymupdf.open(stream=donnees, filetype="pdf")
    except RuntimeError as e:  # pymupdf.FileDataError en dérive
        raise ErreurFichier(f"{nom} : PDF illisible ({e})") from e
    with document:
        if document.needs_pass:
            raise ErreurFichier(f"{nom} : PDF protégé par mot de passe")
        if not any(page.get_text().strip() for page in document):
            raise ErreurFichier(f"{nom} : aucun texte dans ce PDF (document scanné ?) ; l'OCR n'est pas prise en charge")
        # use_ocr=False : sans cela, pymupdf4llm tente une OCR Tesseract si elle est installée.
        return pymupdf4llm.to_markdown(document, use_ocr=False, show_progress=False)
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_texte_pdf.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add obfuscation/src/obfuscation/formats obfuscation/tests/documents.py obfuscation/tests/test_texte_pdf.py
git commit -m "feat(obfuscation): traite les fichiers texte et convertit les PDF en Markdown"
```

---

### Task 7: Parties XML Office et règles Excel

**Files:**
- Create: `obfuscation/src/obfuscation/formats/excel.py`, `obfuscation/src/obfuscation/formats/xml_texte.py`
- Test: `obfuscation/tests/test_xml_texte.py`

**Interfaces:**
- Consumes: `Moteur`, `Sens`, `appliquer` (tâche 4) ; `reecrire` (tâche 5).
- Produces: `xml_texte.transformer_xml(racine: etree._Element, moteur, sens) -> bool` (vrai si la partie a changé) ; constantes `xml_texte.XML_SPACE`, `excel.X`, `excel.C`.

- [ ] **Step 1: Écrire les tests**

`obfuscation/tests/test_xml_texte.py` :

```python
from lxml import etree

from obfuscation.formats.xml_texte import XML_SPACE, transformer_xml

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"


def transformer(xml, moteur, sens="obfusquer"):
    racine = etree.fromstring(xml.encode("utf-8"))
    transformer_xml(racine, moteur, sens)
    return racine


def textes(racine, ns, nom):
    return [e.text or "" for e in racine.iter(f"{{{ns}}}{nom}")]


def test_paragraphe_word_coupe_et_espaces_preserves(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Nova</w:t></w:r>'
        f"<w:r><w:t>ltis SA et</w:t></w:r></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "t") == ["[CLIENT_1]", " et"]
    assert list(racine.iter(f"{{{W}}}t"))[1].get(XML_SPACE) == "preserve"


def test_revision_supprimee_traitee(moteur):
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:del w:author="Jeanne Martin"><w:r><w:delText>Novaltis</w:delText>'
        f"</w:r></w:del></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "delText") == ["[CLIENT_1]"]
    assert next(racine.iter(f"{{{W}}}del")).get(f"{{{W}}}author") == "[PERSONNE_1]"


def test_paragraphes_imbriques_non_fusionnes(moteur):
    # « Nova » (paragraphe externe) et « ltis » (zone de texte) ne forment pas un mot.
    racine = transformer(
        f'<w:document xmlns:w="{W}"><w:p><w:r><w:t>Nova</w:t></w:r><w:r><w:txbxContent><w:p><w:r>'
        f"<w:t>ltis</w:t></w:r></w:p></w:txbxContent></w:r></w:p></w:document>",
        moteur,
    )
    assert textes(racine, W, "t") == ["Nova", "ltis"]


def test_chaines_partagees_texte_enrichi(moteur):
    racine = transformer(
        f'<sst xmlns="{X}"><si><r><t>Nova</t></r><r><rPr><b/></rPr><t>ltis</t></r></si><si><t>Héron</t></si></sst>',
        moteur,
    )
    assert textes(racine, X, "t") == ["[CLIENT_1]", "", "[PROJET_1]"]


def test_metadonnees_et_attributs(moteur):
    racine = transformer(
        f'<racine xmlns:w="{W}" xmlns:wp="{WP}" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:creator>Jeanne Martin</dc:creator>"
        f'<w:comment w:author="Jeanne Martin" w:initials="JM"/>'
        f'<wp:docPr id="1" name="Logo Novaltis" descr="Logo de Novaltis"/></racine>',
        moteur,
    )
    assert textes(racine, "http://purl.org/dc/elements/1.1/", "creator") == ["[PERSONNE_1]"]
    doc_pr = next(racine.iter(f"{{{WP}}}docPr"))
    assert (doc_pr.get("name"), doc_pr.get("descr")) == ("Logo [CLIENT_1]", "Logo de [CLIENT_1]")


def test_seuls_les_liens_externes_sont_traites(moteur):
    racine = transformer(
        f'<Relationships xmlns="{REL}">'
        f'<Relationship Id="rId1" Type="h" Target="mailto:jeanne.martin@novaltis.example" TargetMode="External"/>'
        f'<Relationship Id="rId2" Type="i" Target="media/novaltis.png"/></Relationships>',
        moteur,
    )
    cibles = [r.get("Target") for r in racine.iter(f"{{{REL}}}Relationship")]
    assert cibles == ["mailto:[EMAIL_1]", "media/novaltis.png"]


def test_cellules(moteur):
    racine = transformer(
        f'<worksheet xmlns="{X}"><sheetData><row r="1">'
        f'<c r="A1" t="s"><v>123456782</v></c>'
        f'<c r="B1" t="str"><f>A1</f><v>Novaltis</v></c>'
        f'<c r="C1"><v>123456782</v></c>'
        f'<c r="D1"><v>42</v></c>'
        f"</row></sheetData></worksheet>",
        moteur,
    )
    cellules = {c.get("r"): c for c in racine.iter(f"{{{X}}}c")}
    assert cellules["A1"].findtext(f"{{{X}}}v") == "123456782"  # index de chaîne partagée : intact
    assert cellules["B1"].findtext(f"{{{X}}}v") == "[CLIENT_1]"  # résultat texte d'une formule
    assert cellules["C1"].get("t") == "inlineStr"
    assert cellules["C1"].findtext(f"{{{X}}}is/{{{X}}}t") == "[SIREN_1]"
    assert cellules["D1"].findtext(f"{{{X}}}v") == "42"


def test_caches_de_graphique(moteur):
    racine = transformer(
        f'<c:chartSpace xmlns:c="{C}"><c:strCache><c:pt idx="0"><c:v>Novaltis</c:v></c:pt></c:strCache>'
        f'<c:numCache><c:pt idx="0"><c:v>123456782</c:v></c:pt></c:numCache></c:chartSpace>',
        moteur,
    )
    assert textes(racine, C, "v") == ["[CLIENT_1]", "123456782"]


def test_noms_de_feuilles_et_formules(moteur):
    racine = transformer(
        f'<workbook xmlns="{X}"><sheets><sheet name="Novaltis SA" sheetId="1"/><sheet name="Budget Héron" sheetId="2"/>'
        f"</sheets><definedNames><definedName name=\"Zone\">'Novaltis SA'!$A$1</definedName></definedNames>"
        f'<f>SUM(Novaltis!A1:A3)&amp;"Novaltis"</f></workbook>',
        moteur,
    )
    assert [s.get("name") for s in racine.iter(f"{{{X}}}sheet")] == ["CLIENT_1", "Budget PROJET_1"]
    assert textes(racine, X, "definedName") == ["'CLIENT_1'!$A$1"]
    assert textes(racine, X, "f") == ['SUM(CLIENT_1!A1:A3)&"[CLIENT_1]"']


def test_formules_restaurees_avec_guillemets_si_besoin(moteur):
    moteur.transformer("Projet Héron, Jeanne Martin", "obfusquer")
    racine = transformer(
        f"<worksheet xmlns=\"{X}\"><f>'Budget PROJET_1'!A1&amp;PERSONNE_1!B2</f></worksheet>", moteur, "restaurer"
    )
    assert textes(racine, X, "f") == ["'Budget Projet Héron'!A1&'Jeanne Martin'!B2"]


def test_nom_de_feuille_invalide_a_la_restauration(moteur):
    moteur.transformer("https://intranet.novaltis.fr/a", "obfusquer")
    racine = transformer(f'<workbook xmlns="{X}"><sheets><sheet name="URL_1"/></sheets></workbook>', moteur, "restaurer")
    assert next(racine.iter(f"{{{X}}}sheet")).get("name") == "URL_1"
    assert any("URL_1" in a for a in moteur.avertissements)


def test_en_tete_excel_avec_codes(moteur):
    racine = transformer(
        f'<worksheet xmlns="{X}"><headerFooter><oddHeader>&amp;CNovaltis &amp;"Arial,Gras"Héron</oddHeader>'
        f"</headerFooter></worksheet>",
        moteur,
    )
    assert textes(racine, X, "oddHeader") == ['&C[CLIENT_1] &"Arial,Gras"[PROJET_1]']
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_xml_texte.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.formats.xml_texte'`

- [ ] **Step 3: Implémenter les règles Excel**

`obfuscation/src/obfuscation/formats/excel.py` :

```python
"""Règles propres à Excel : formules, noms de feuilles, en-têtes et cellules numériques."""
import re
from dataclasses import replace

from lxml import etree

from ..moteur import Moteur, Sens, appliquer

X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"

FORMULES = {f"{{{X}}}f", f"{{{C}}}f", f"{{{X}}}definedName"}
EN_TETES = {f"{{{X}}}{nom}" for nom in ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter")}
FEUILLE = f"{{{X}}}sheet"
CELLULE = f"{{{X}}}c"
VALEUR = f"{{{X}}}v"
VALEUR_GRAPHIQUE = f"{{{C}}}v"

# Référence à une feuille dans une formule : 'Nom avec espaces'!A1 ou Nom!A1
REFERENCE_FEUILLE = re.compile(r"'(?:[^']|'')+'(?=!)|[^\W\d][\w.]*(?=!)")
NOM_SIMPLE = re.compile(r"[^\W\d][\w.]*")
# Codes de mise en forme des en-têtes : &C, &"Arial,Gras", &12, &K00FF00, &&…
CODE_EN_TETE = re.compile(r'&(?:"[^"]*"|\d+|K[0-9A-Fa-f]{6}|.)', re.DOTALL)
CARACTERES_INTERDITS_FEUILLE = set("[]:*?/\\")
LONGUEUR_MAX_FEUILLE = 31


def nom_de_feuille(nom: str, moteur: Moteur, sens: Sens) -> str:
    """Les crochets sont interdits dans un nom de feuille : on y écrit le jeton nu (CLIENT_1)."""
    if sens == "obfusquer":
        return appliquer(nom, [replace(r, texte=r.jeton) for r in moteur.remplacements(nom, sens)])
    restaure = moteur.transformer(nom, sens)
    if not restaure or len(restaure) > LONGUEUR_MAX_FEUILLE or CARACTERES_INTERDITS_FEUILLE & set(restaure):
        moteur.avertissements.append(f"nom de feuille « {nom} » laissé tel quel : « {restaure} » n'est pas un nom de feuille valide")
        return nom
    return restaure


def traiter_nom_de_feuille(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    nom = element.get("name", "")
    nouveau = nom_de_feuille(nom, moteur, sens)
    if nouveau == nom:
        return False
    element.set("name", nouveau)
    return True


def _citer(nom: str) -> str:
    return "'" + nom.replace("'", "''") + "'"


def traiter_formule(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Les références de feuilles suivent la règle des noms de feuilles ; le reste, la règle générale."""
    texte = element.text or ""
    morceaux, curseur = [], 0
    for m in REFERENCE_FEUILLE.finditer(texte):
        morceaux.append(moteur.transformer(texte[curseur:m.start()], sens))
        reference = m.group()
        citee = reference.startswith("'")
        nom = nom_de_feuille(reference[1:-1].replace("''", "'") if citee else reference, moteur, sens)
        morceaux.append(_citer(nom) if citee or not NOM_SIMPLE.fullmatch(nom) else nom)
        curseur = m.end()
    morceaux.append(moteur.transformer(texte[curseur:], sens))
    nouveau = "".join(morceaux)
    if nouveau == texte:
        return False
    element.text = nouveau
    return True


def traiter_en_tete(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    texte = element.text or ""
    morceaux, curseur = [], 0
    for m in CODE_EN_TETE.finditer(texte):
        morceaux += [moteur.transformer(texte[curseur:m.start()], sens), m.group()]
        curseur = m.end()
    morceaux.append(moteur.transformer(texte[curseur:], sens))
    nouveau = "".join(morceaux)
    if nouveau == texte:
        return False
    element.text = nouveau
    return True


def traiter_cellule_numerique(cellule: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Un nombre qui est un SIRET, un SIREN ou un téléphone devient une chaîne obfusquée."""
    if sens != "obfusquer" or cellule.get("t", "n") != "n" or cellule.find(f"{{{X}}}f") is not None:
        return False
    valeur = cellule.find(VALEUR)
    if valeur is None or not (valeur.text or "").isdigit():
        return False
    remplacements = moteur.remplacements(valeur.text, sens)
    if not remplacements:
        return False
    texte = appliquer(valeur.text, remplacements)
    cellule.set("t", "inlineStr")
    cellule.remove(valeur)
    chaine = etree.SubElement(cellule, f"{{{X}}}is")
    etree.SubElement(chaine, f"{{{X}}}t").text = texte
    return True


def texte_exclu(element: etree._Element) -> bool:
    """Valeurs qui ne sont pas du texte : nombres, index de chaînes partagées, caches numériques de graphiques."""
    if element.tag == VALEUR:
        parent = element.getparent()
        return parent is None or parent.get("t") != "str"
    if element.tag == VALEUR_GRAPHIQUE:
        return any(etree.QName(a).localname in ("numCache", "numLit") for a in element.iterancestors())
    return False
```

- [ ] **Step 4: Implémenter le traitement des parties XML**

`obfuscation/src/obfuscation/formats/xml_texte.py` :

```python
"""Remplacements dans une partie XML d'un document Office (Word, Excel, PowerPoint)."""
from lxml import etree

from ..moteur import Moteur, Sens
from ..segments import reecrire
from . import excel

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
X = excel.X
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _q(ns: str, nom: str) -> str:
    return f"{{{ns}}}{nom}"


# Unité de texte (paragraphe, chaîne Excel, commentaire) → éléments qui portent ses segments.
UNITES = {
    _q(W, "p"): (_q(W, "t"), _q(W, "delText")),
    _q(A, "p"): (_q(A, "t"),),
    _q(X, "si"): (_q(X, "t"),),
    _q(X, "is"): (_q(X, "t"),),
    _q(X, "text"): (_q(X, "t"),),
}
SEGMENTS = {tag for tags in UNITES.values() for tag in tags}
PRESERVER_ESPACES = {_q(W, "t"), _q(W, "delText"), _q(X, "t")}
# Attributs lisibles : relecteurs, textes de remplacement des images, info-bulles…
ATTRIBUTS = {"author", "initials", "descr", "title", "tooltip", "userName"}
ATTRIBUTS_PAR_ELEMENT = {
    ("cNvPr", "name"),
    ("docPr", "name"),
    ("person", "displayName"),
    ("tblCaption", "val"),
    ("tblDescription", "val"),
}


def transformer_xml(racine: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Applique le moteur à une partie ; renvoie vrai si elle a changé."""
    modifie = False
    for unite in racine.iter(*UNITES):
        segments = [s for s in unite.iter(*UNITES[unite.tag]) if _unite(s) is unite]
        modifie |= _traiter_segments(segments, moteur, sens)
    # Liste figée : traiter_cellule_numerique modifie l'arbre pendant le parcours.
    for element in list(racine.iter(tag=etree.Element)):
        if element.tag in SEGMENTS and _unite(element) is not None:
            pass  # déjà traité avec son unité
        elif element.tag in excel.FORMULES:
            modifie |= excel.traiter_formule(element, moteur, sens)
        elif element.tag in excel.EN_TETES:
            modifie |= excel.traiter_en_tete(element, moteur, sens)
        elif element.tag == excel.CELLULE:
            modifie |= excel.traiter_cellule_numerique(element, moteur, sens)
        elif element.text and element.text.strip() and not excel.texte_exclu(element):
            modifie |= _traiter_texte(element, moteur, sens)
        modifie |= _traiter_attributs(element, moteur, sens)
    return modifie


def _unite(element: etree._Element) -> etree._Element | None:
    """Unité la plus proche : une zone de texte imbriquée forme sa propre unité."""
    return next(element.iterancestors(*UNITES), None)


def _traiter_segments(segments: list[etree._Element], moteur: Moteur, sens: Sens) -> bool:
    textes = [s.text or "" for s in segments]
    remplacements = moteur.remplacements("".join(textes), sens)
    if not remplacements:
        return False
    for segment, texte in zip(segments, reecrire(textes, remplacements)):
        segment.text = texte
        if segment.tag in PRESERVER_ESPACES and texte != texte.strip():
            segment.set(XML_SPACE, "preserve")
    return True


def _traiter_texte(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    nouveau = moteur.transformer(element.text, sens)
    if nouveau == element.text:
        return False
    element.text = nouveau
    return True


def _traiter_attributs(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    modifie = False
    local = etree.QName(element).localname
    for nom, valeur in element.attrib.items():
        attribut = etree.QName(nom).localname
        lien_externe = local == "Relationship" and attribut == "Target" and element.get("TargetMode") == "External"
        if attribut in ATTRIBUTS or (local, attribut) in ATTRIBUTS_PAR_ELEMENT or lien_externe:
            nouveau = moteur.transformer(valeur, sens)
            if nouveau != valeur:
                element.set(nom, nouveau)
                modifie = True
    if element.tag == excel.FEUILLE:
        modifie |= excel.traiter_nom_de_feuille(element, moteur, sens)
    return modifie
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_xml_texte.py -v`
Expected: PASS (12 tests)

- [ ] **Step 6: Commit**

```bash
git add obfuscation/src/obfuscation/formats/excel.py obfuscation/src/obfuscation/formats/xml_texte.py obfuscation/tests/test_xml_texte.py
git commit -m "feat(obfuscation): traite le texte des parties XML Office et les règles Excel"
```

---

### Task 8: Contrôle résiduel

**Files:**
- Create: `obfuscation/src/obfuscation/controle.py`, `obfuscation/src/obfuscation/formats/ooxml.py` (constantes et `lire_xml` seulement ; complété à la tâche 9)
- Modify: `obfuscation/tests/documents.py` (ajout de `zip_de`)
- Test: `obfuscation/tests/test_controle.py`

**Interfaces:**
- Consumes: `Dictionnaire.variantes`, `motif_de_terme` (tâche 2), `Table.jetons` (tâche 1).
- Produces: `formats.ooxml.EXTENSIONS_OOXML`, `EXTENSIONS_IMAGES`, `lire_xml(contenu: bytes) -> etree._Element` ; `controle.Controle(dictionnaire, table)` avec `.chercher(texte: str) -> set[str]`, `.controler_texte(donnees: bytes) -> list[str]` (éléments `« terme »`), `.controler_ooxml(donnees: bytes, prefixe: str = "") -> list[str]` (éléments `partie : « terme »`) ; `documents.zip_de(parties: dict[str, bytes]) -> bytes`.

- [ ] **Step 1: Fabrique d'archives de test**

Ajouter à `obfuscation/tests/documents.py` (imports en tête du fichier, fonction après `pdf_exemple`) :

```python
import io
import zipfile


def zip_de(parties: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in parties.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()
```

- [ ] **Step 2: Écrire les tests**

`obfuscation/tests/test_controle.py` :

```python
from documents import zip_de

from obfuscation.controle import Controle
from obfuscation.table import Table

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_texte_propre_et_texte_avec_fuite(dictionnaire):
    controle = Controle(dictionnaire, Table())
    assert controle.controler_texte("[CLIENT_1] signe.".encode()) == []
    assert controle.controler_texte("Signé : NOVALTIS".encode()) == ["« NOVALTIS »"]


def test_valeurs_de_la_table_recherchees(dictionnaire):
    table = Table()
    table.jeton_pour("EMAIL", "contact@acme.example")
    assert Controle(dictionnaire, table).controler_texte(b"ecrire a contact@acme.example") == ["« contact@acme.example »"]


def test_terme_dans_un_attribut_non_traite(dictionnaire):
    document = zip_de({
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:p><w:fldSimple w:instr="HYPERLINK https://novaltis.fr"/>'
        f"</w:p></w:document>".encode(),
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["word/document.xml : « novaltis »"]


def test_terme_coupe_entre_segments(dictionnaire):
    document = zip_de({
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:p><w:r><w:t>Nova</w:t></w:r><w:r><w:t>ltis</w:t>'
        f"</w:r></w:p></w:document>".encode(),
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["word/document.xml : « Novaltis »"]


def test_document_incorpore_binaire_et_image(dictionnaire):
    classeur = zip_de({"xl/sharedStrings.xml": b"<sst><si><t>H\xc3\xa9ron</t></si></sst>"})
    document = zip_de({
        "word/embeddings/Classeur.xlsx": classeur,
        "word/embeddings/oleObject1.bin": b"  " + "Novaltis".encode("utf-16-le"),
        "word/media/image1.png": b"\x89PNG Novaltis",
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == [
        "word/embeddings/Classeur.xlsx › xl/sharedStrings.xml : « Héron »",
        "word/embeddings/oleObject1.bin : « Novaltis »",
    ]
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_controle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'obfuscation.controle'`

- [ ] **Step 4: Implémenter**

`obfuscation/src/obfuscation/formats/ooxml.py` (première partie ; la tâche 9 ajoute la transformation) :

```python
"""Documents Office (docx, xlsx, pptx) : des archives zip de parties XML."""
from lxml import etree

EXTENSIONS_OOXML = {".docx", ".xlsx", ".pptx"}
EXTENSIONS_XML = {".xml", ".rels", ".vml"}
EXTENSIONS_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf", ".svg"}
PARSEUR = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def lire_xml(contenu: bytes) -> etree._Element:
    return etree.fromstring(contenu, PARSEUR)
```

`obfuscation/src/obfuscation/controle.py` :

```python
"""Contrôle résiduel : relit un fichier produit et y cherche tout terme sensible, sans passer par les règles de format."""
import io
import re
import zipfile
from pathlib import PurePosixPath

from lxml import etree

from .dictionnaire import Dictionnaire, motif_de_terme
from .formats.ooxml import EXTENSIONS_IMAGES, EXTENSIONS_OOXML, lire_xml
from .table import Table


class Controle:
    """Cherche les variantes des dictionnaires et toutes les valeurs déjà enregistrées dans la table."""

    def __init__(self, dictionnaire: Dictionnaire, table: Table):
        termes = {*dictionnaire.variantes, *table.jetons.values()}
        alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
        self._regex = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE) if termes else None

    def chercher(self, texte: str) -> set[str]:
        if self._regex is None:
            return set()
        return {m.group() for m in self._regex.finditer(texte)}

    def controler_texte(self, donnees: bytes) -> list[str]:
        return [f"« {terme} »" for terme in sorted(self.chercher(donnees.decode("utf-8", errors="replace")))]

    def controler_ooxml(self, donnees: bytes, prefixe: str = "") -> list[str]:
        fuites = []
        with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
            for info in archive.infolist():
                contenu = archive.read(info)
                partie = prefixe + info.filename
                extension = PurePosixPath(info.filename).suffix.lower()
                if extension in EXTENSIONS_OOXML:
                    fuites += self.controler_ooxml(contenu, f"{partie} › ")
                elif extension not in EXTENSIONS_IMAGES:
                    fuites += [f"{partie} : « {terme} »" for terme in sorted(self._chercher_partie(contenu))]
        return fuites

    def _chercher_partie(self, contenu: bytes) -> set[str]:
        try:
            racine = lire_xml(contenu)
        except (etree.XMLSyntaxError, ValueError):
            # Partie binaire ou XML mal formé : recherche brute, en UTF-8 et en UTF-16 (objets OLE).
            return self.chercher(contenu.decode("utf-8", errors="replace")) | self.chercher(
                contenu.decode("utf-16-le", errors="replace")
            )
        elements = list(racine.iter(tag=etree.Element))
        trouves = set()
        for element in elements:
            for texte in (element.text, element.tail, *element.attrib.values()):
                if texte:
                    trouves |= self.chercher(texte)
        # Un terme coupé entre deux segments n'apparaît que dans le texte mis bout à bout.
        return trouves | self.chercher("".join(e.text or "" for e in elements))
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_controle.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add obfuscation/src/obfuscation/controle.py obfuscation/src/obfuscation/formats/ooxml.py obfuscation/tests/documents.py obfuscation/tests/test_controle.py
git commit -m "feat(obfuscation): ajoute le contrôle résiduel des fichiers produits"
```

---

### Task 9: Documents Office complets (zip, récursion, miniature)

**Files:**
- Modify: `obfuscation/src/obfuscation/formats/ooxml.py`, `obfuscation/tests/documents.py`
- Test: `obfuscation/tests/test_ooxml.py`

**Interfaces:**
- Consumes: `transformer_xml` (tâche 7), `Resultat` (tâche 6), `ErreurFichier`, `lire_xml` et constantes (tâche 8).
- Produces: `formats.ooxml.transformer_ooxml(donnees: bytes, moteur, sens, nom: str = "document") -> Resultat` ; dans `documents.py` : `docx_exemple()`, `xlsx_exemple()`, `pptx_exemple()`, `modifier_partie(donnees, nom, modification)`, `ajouter_partie(donnees, nom, contenu)`, `sensibles(donnees) -> set[str]`, `png_1x1()`, constante `SENSIBLES`.

- [ ] **Step 1: Fabriques de documents Office**

Compléter `obfuscation/tests/documents.py` pour qu'il contienne, dans cet ordre, la docstring, les imports ci-dessous, `DICO`, puis les fonctions existantes (`pdf_exemple`, `zip_de`) et les nouvelles :

```python
"""Fabrique des documents de test : aucun binaire n'est versionné."""
import io
import struct
import zipfile
import zlib
from collections.abc import Callable

import openpyxl
import pymupdf
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from openpyxl.comments import Comment
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SENSIBLES = ("novaltis", "héron", "jeanne martin", "jeanne.martin", "12345678200010", "123 456 782")
```

Nouvelles fonctions :

```python
def png_1x1() -> bytes:
    def bloc(type_: bytes, donnees: bytes) -> bytes:
        return struct.pack(">I", len(donnees)) + type_ + donnees + struct.pack(">I", zlib.crc32(type_ + donnees))

    return (
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + bloc(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + bloc(b"IEND", b"")
    )


def modifier_partie(donnees: bytes, nom: str, modification: Callable[[bytes], bytes]) -> bytes:
    """Réécrit (ou ajoute) une partie d'une archive Office."""
    with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
        parties = {info.filename: archive.read(info) for info in archive.infolist()}
    parties[nom] = modification(parties.get(nom, b""))
    return zip_de(parties)


def ajouter_partie(donnees: bytes, nom: str, contenu: bytes) -> bytes:
    return modifier_partie(donnees, nom, lambda _ancien: contenu)


def _enregistrer(document) -> bytes:
    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


def _ajouter_revision(xml: bytes) -> bytes:
    revision = (
        f'<w:p xmlns:w="{W}"><w:del w:id="90" w:author="Jeanne Martin"><w:r>'
        f"<w:delText>Ancien client : Novaltis</w:delText></w:r></w:del></w:p>"
    )
    return xml.replace(b"<w:sectPr", revision.encode() + b"<w:sectPr", 1)


def xlsx_exemple() -> bytes:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Novaltis"
    feuille["A1"] = "Client Novaltis SA"
    feuille["A1"].comment = Comment("Validé par Jeanne Martin", "Jeanne Martin")
    feuille["A2"] = 12345678200010
    feuille["A3"] = "Projet Héron"
    feuille.oddHeader.center.text = "Novaltis confidentiel"
    calcul = classeur.create_sheet("Calcul")
    calcul["A1"] = "=Novaltis!A1"
    calcul["A2"] = '="Novaltis"&" SA"'
    classeur.properties.creator = "Jeanne Martin"
    return _enregistrer(classeur)


def docx_exemple() -> bytes:
    document = Document()
    paragraphe = document.add_paragraph()
    paragraphe.add_run("Nova").bold = True
    paragraphe.add_run("ltis SA signe le Projet Héron.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Contact : jeanne.martin@novaltis.example"
    document.sections[0].header.paragraphs[0].text = "Novaltis – confidentiel"
    relu = document.add_paragraph("Relu.")
    document.add_comment(relu.runs, text="Validé par Jeanne Martin", author="Jeanne Martin", initials="JM")
    document.add_picture(io.BytesIO(png_1x1()))
    document.part.relate_to("mailto:jeanne.martin@novaltis.example", RT.HYPERLINK, is_external=True)
    document.core_properties.author = "Jeanne Martin"
    document.core_properties.title = "Proposition Novaltis"
    donnees = modifier_partie(_enregistrer(document), "word/document.xml", _ajouter_revision)
    note = f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1"><w:p><w:r><w:t>Voir Novaltis</w:t></w:r></w:p></w:footnote></w:footnotes>'
    donnees = ajouter_partie(donnees, "word/footnotes.xml", note.encode())
    return ajouter_partie(donnees, "word/embeddings/Classeur.xlsx", xlsx_exemple())


def pptx_exemple() -> bytes:
    presentation = Presentation()
    diapo = presentation.slides.add_slide(presentation.slide_layouts[5])
    diapo.shapes.title.text = "Projet Héron"
    paragraphe = diapo.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1)).text_frame.paragraphs[0]
    paragraphe.add_run().text = "Nova"
    suite = paragraphe.add_run()
    suite.text = "ltis pilote."
    suite.font.bold = True
    diapo.notes_slide.notes_text_frame.text = "Appeler Jeanne Martin"
    donnees = CategoryChartData()
    donnees.categories = ["Novaltis", "Autre"]
    donnees.add_series("Charge", (3, 5))
    diapo.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(3), Inches(4), Inches(3), donnees)
    presentation.core_properties.author = "Jeanne Martin"
    return _enregistrer(presentation)


def texte_brut(donnees: bytes) -> str:
    """Tout le contenu décompressé de l'archive, documents incorporés compris."""
    morceaux = []
    with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
        for info in archive.infolist():
            contenu = archive.read(info)
            if info.filename.endswith((".docx", ".xlsx", ".pptx")):
                morceaux.append(texte_brut(contenu))
            else:
                morceaux.append(contenu.decode("utf-8", errors="ignore"))
    return "\n".join(morceaux)


def sensibles(donnees: bytes) -> set[str]:
    brut = texte_brut(donnees).casefold()
    return {terme for terme in SENSIBLES if terme in brut}
```

- [ ] **Step 2: Écrire les tests**

`obfuscation/tests/test_ooxml.py` :

```python
import io
import zipfile

import openpyxl
import pytest
from docx import Document
from documents import SENSIBLES, ajouter_partie, docx_exemple, modifier_partie, pptx_exemple, sensibles, xlsx_exemple
from pptx import Presentation

from obfuscation.erreurs import ErreurFichier
from obfuscation.formats.ooxml import transformer_ooxml


def obfusquer(donnees, moteur):
    return transformer_ooxml(donnees, moteur, "obfusquer")


def test_les_exemples_contiennent_bien_les_termes():
    assert sensibles(docx_exemple()) >= {"novaltis", "héron", "jeanne martin", "jeanne.martin"}
    assert sensibles(xlsx_exemple()) >= {"novaltis", "héron", "jeanne martin", "12345678200010"}


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_aucun_terme_ne_subsiste(moteur, fabrique):
    assert sensibles(obfusquer(fabrique(), moteur).donnees) == set()


def test_docx_mise_en_forme_conservee(moteur):
    document = Document(io.BytesIO(obfusquer(docx_exemple(), moteur).donnees))
    premier = document.paragraphs[0]
    assert premier.text == "[CLIENT_1] signe le [PROJET_1]."
    assert premier.runs[0].text == "[CLIENT_1]" and premier.runs[0].bold
    assert document.sections[0].header.paragraphs[0].text == "[CLIENT_1] – confidentiel"
    assert document.core_properties.author == "[PERSONNE_1]"


def test_docx_miniature_retiree_images_intactes(moteur):
    original = docx_exemple()
    resultat = obfusquer(original, moteur)
    avant, apres = zipfile.ZipFile(io.BytesIO(original)), zipfile.ZipFile(io.BytesIO(resultat.donnees))
    assert "docProps/thumbnail.jpeg" in avant.namelist()
    assert "docProps/thumbnail.jpeg" not in apres.namelist()
    assert b"thumbnail" not in apres.read("_rels/.rels")
    assert apres.read("word/media/image1.png") == avant.read("word/media/image1.png")
    assert any("1 image(s)" in a for a in resultat.avertissements)


def test_docx_aller_retour(moteur):
    original = docx_exemple()
    restaure = transformer_ooxml(obfusquer(original, moteur).donnees, moteur, "restaurer").donnees

    def textes(donnees):
        return [p.text for p in Document(io.BytesIO(donnees)).paragraphs]

    assert textes(restaure) == [t.replace("Novaltis SA", "Novaltis") for t in textes(original)]


def test_xlsx_feuilles_formules_cellules(moteur):
    classeur = openpyxl.load_workbook(io.BytesIO(obfusquer(xlsx_exemple(), moteur).donnees))
    assert classeur.sheetnames == ["CLIENT_1", "Calcul"]
    feuille = classeur["CLIENT_1"]
    assert feuille["A1"].value == "Client [CLIENT_1]"
    assert "[PERSONNE_1]" in feuille["A1"].comment.text
    assert feuille["A2"].value == "[SIRET_1]"
    assert feuille.oddHeader.center.text == "[CLIENT_1] confidentiel"
    assert classeur["Calcul"]["A1"].value == "=CLIENT_1!A1"
    assert classeur["Calcul"]["A2"].value == '="[CLIENT_1]"&" SA"'


def test_xlsx_aller_retour(moteur):
    restaure = transformer_ooxml(obfusquer(xlsx_exemple(), moteur).donnees, moteur, "restaurer").donnees
    classeur = openpyxl.load_workbook(io.BytesIO(restaure))
    assert classeur.sheetnames == ["Novaltis", "Calcul"]
    assert classeur["Calcul"]["A1"].value == "=Novaltis!A1"
    assert classeur["Novaltis"]["A2"].value == "12345678200010"


def test_xlsx_vml_mal_forme_recopie(moteur):
    original = ajouter_partie(xlsx_exemple(), "xl/drawings/vmlDrawing9.vml", b"<xml><br></xml>")
    resultat = zipfile.ZipFile(io.BytesIO(obfusquer(original, moteur).donnees))
    assert resultat.read("xl/drawings/vmlDrawing9.vml") == b"<xml><br></xml>"


def test_pptx_diapo_notes_et_graphique(moteur):
    presentation = Presentation(io.BytesIO(obfusquer(pptx_exemple(), moteur).donnees))
    diapo = presentation.slides[0]
    assert diapo.shapes.title.text == "[PROJET_1]"
    zone = diapo.shapes[1].text_frame.paragraphs[0]
    assert [r.text for r in zone.runs] == ["[CLIENT_1]", " pilote."]
    assert not zone.runs[0].font.bold and zone.runs[1].font.bold
    assert diapo.notes_slide.notes_text_frame.text == "Appeler [PERSONNE_1]"
    graphique = next(s for s in diapo.shapes if s.has_chart).chart
    assert list(graphique.plots[0].categories) == ["[CLIENT_1]", "Autre"]


def test_objet_ole_signale(moteur):
    original = ajouter_partie(docx_exemple(), "word/embeddings/oleObject1.bin", b"\x00\x01")
    assert any("oleObject1.bin" in a for a in obfusquer(original, moteur).avertissements)


def test_archive_invalide(moteur):
    with pytest.raises(ErreurFichier, match="illisible"):
        transformer_ooxml(b"pas une archive", moteur, "obfusquer", "casse.docx")


def test_partie_xml_invalide(moteur):
    casse = modifier_partie(docx_exemple(), "word/document.xml", lambda _xml: b"<w:document")
    with pytest.raises(ErreurFichier, match="word/document.xml"):
        transformer_ooxml(casse, moteur, "obfusquer", "casse.docx")
```

- [ ] **Step 3: Vérifier l'échec**

Run: `uv run pytest tests/test_ooxml.py -v`
Expected: FAIL — `ImportError: cannot import name 'transformer_ooxml'`

- [ ] **Step 4: Implémenter**

Remplacer le contenu de `obfuscation/src/obfuscation/formats/ooxml.py` par :

```python
"""Documents Office (docx, xlsx, pptx) : des archives zip de parties XML."""
import io
import zipfile
from pathlib import PurePosixPath

from lxml import etree

from ..erreurs import ErreurFichier
from ..moteur import Moteur, Sens
from . import Resultat
from .xml_texte import transformer_xml

EXTENSIONS_OOXML = {".docx", ".xlsx", ".pptx"}
EXTENSIONS_XML = {".xml", ".rels", ".vml"}
EXTENSIONS_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf", ".svg"}
RELATIONS = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
TYPE_MINIATURE = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"
PARSEUR = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def lire_xml(contenu: bytes) -> etree._Element:
    return etree.fromstring(contenu, PARSEUR)


def transformer_ooxml(donnees: bytes, moteur: Moteur, sens: Sens, nom: str = "document") -> Resultat:
    """Transforme chaque partie XML ; tout le reste est recopié à l'identique, dans le même ordre."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(donnees))
    except zipfile.BadZipFile as e:
        raise ErreurFichier(f"{nom} : document Office illisible (fichier corrompu ou protégé par mot de passe)") from e
    avertissements: list[str] = []
    images = 0
    sortie = io.BytesIO()
    with archive, zipfile.ZipFile(sortie, "w") as resultat:
        # La miniature est une image de la première page : elle montrerait le texte en clair.
        miniatures = _miniatures(archive) if sens == "obfusquer" else set()
        for info in archive.infolist():
            if info.filename in miniatures:
                continue
            contenu = archive.read(info)
            extension = PurePosixPath(info.filename).suffix.lower()
            if extension in EXTENSIONS_XML:
                contenu = _transformer_partie(contenu, info.filename, moteur, sens, miniatures, nom)
            elif extension in EXTENSIONS_OOXML:
                incorpore = transformer_ooxml(contenu, moteur, sens, f"{nom} › {info.filename}")
                contenu = incorpore.donnees
                avertissements += incorpore.avertissements
            elif extension in EXTENSIONS_IMAGES:
                images += 1
            elif "/embeddings/" in info.filename and sens == "obfusquer":
                avertissements.append(f"{nom} : objet incorporé non traité ({info.filename})")
            resultat.writestr(info, contenu)
    if images and sens == "obfusquer":
        avertissements.append(f"{nom} : {images} image(s) non analysée(s) ; le texte qu'elles contiennent reste lisible")
    return Resultat(sortie.getvalue(), avertissements)


def _miniatures(archive: zipfile.ZipFile) -> set[str]:
    try:
        racine = lire_xml(archive.read("_rels/.rels"))
    except (KeyError, etree.XMLSyntaxError):
        return set()
    return {
        relation.get("Target", "").lstrip("/")
        for relation in racine.iter(f"{{{RELATIONS}}}Relationship")
        if relation.get("Type") == TYPE_MINIATURE
    }


def _transformer_partie(contenu: bytes, partie: str, moteur: Moteur, sens: Sens, miniatures: set[str], nom: str) -> bytes:
    try:
        racine = lire_xml(contenu)
    except etree.XMLSyntaxError as e:
        if partie.endswith(".vml"):
            return contenu  # VML hérité, souvent mal formé : le contrôle résiduel le vérifie en texte brut
        raise ErreurFichier(f"{nom} : partie XML illisible ({partie})") from e
    modifie = transformer_xml(racine, moteur, sens)
    if miniatures:
        modifie |= _retirer_miniatures(racine, miniatures)
    if not modifie:
        return contenu
    arbre = racine.getroottree()
    return etree.tostring(arbre, xml_declaration=True, encoding="UTF-8", standalone=arbre.docinfo.standalone)


def _retirer_miniatures(racine: etree._Element, miniatures: set[str]) -> bool:
    """Retire la relation vers la miniature et sa déclaration de type."""
    a_retirer = [r for r in racine.iter(f"{{{RELATIONS}}}Relationship") if r.get("Type") == TYPE_MINIATURE]
    a_retirer += [o for o in racine.iter(f"{{{TYPES}}}Override") if o.get("PartName", "").lstrip("/") in miniatures]
    for element in a_retirer:
        element.getparent().remove(element)
    return bool(a_retirer)
```

- [ ] **Step 5: Vérifier le succès**

Run: `uv run pytest tests/test_ooxml.py tests/test_controle.py -v`
Expected: PASS (14 + 5 tests)

- [ ] **Step 6: Commit**

```bash
git add obfuscation/src/obfuscation/formats/ooxml.py obfuscation/tests/documents.py obfuscation/tests/test_ooxml.py
git commit -m "feat(obfuscation): obfusque les documents Word, Excel et PowerPoint"
```

---

### Task 10: Vérification croisée contrôle / formats

**Files:**
- Test: `obfuscation/tests/test_controle.py` (ajout)

**Interfaces:**
- Consumes: `transformer_ooxml` (tâche 9), `Controle` (tâche 8), fabriques de `documents.py`.
- Produces: aucune interface nouvelle ; garantit que les exemples obfusqués passent le contrôle (sinon tout fichier réel serait marqué `NON-CONFORME_`).

- [ ] **Step 1: Écrire le test**

Ajouter à `obfuscation/tests/test_controle.py` :

```python
import pytest
from documents import docx_exemple, pptx_exemple, xlsx_exemple

from obfuscation.formats.ooxml import transformer_ooxml


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_documents_obfusques_conformes(moteur, fabrique):
    donnees = transformer_ooxml(fabrique(), moteur, "obfusquer").donnees
    assert Controle(moteur.dictionnaire, moteur.table).controler_ooxml(donnees) == []


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_documents_originaux_non_conformes(moteur, fabrique):
    assert Controle(moteur.dictionnaire, moteur.table).controler_ooxml(fabrique()) != []
```

(Placer les imports en tête du fichier avec les autres.)

- [ ] **Step 2: Lancer**

Run: `uv run pytest tests/test_controle.py -v`
Expected: PASS (11 tests). Si `test_documents_obfusques_conformes` échoue, le message liste la partie et le terme : corriger la règle manquante dans `xml_texte.py` (attribut à ajouter à `ATTRIBUTS`/`ATTRIBUTS_PAR_ELEMENT`, ou élément à traiter), ajouter un test ciblé dans `test_xml_texte.py`, et relancer `uv run pytest`.

- [ ] **Step 3: Commit**

```bash
git add obfuscation/tests/test_controle.py
git commit -m "test(obfuscation): vérifie que les documents obfusqués passent le contrôle"
```

---

### Task 11: Commandes `obfusquer` et `restaurer`

**Files:**
- Create: `obfuscation/src/obfuscation/cli.py`
- Test: `obfuscation/tests/test_cli.py`

**Interfaces:**
- Consumes: tout ce qui précède.
- Produces: `cli.main_obfusquer(argv: list[str] | None = None) -> int`, `cli.main_restaurer(argv: list[str] | None = None) -> int` (points d'entrée `obfusquer` / `restaurer` du `pyproject.toml`) ; `cli._transformer(source: Path, moteur, sens) -> Resultat` (remplacé dans un test).

- [ ] **Step 1: Écrire les tests**

`obfuscation/tests/test_cli.py` :

```python
import io
import json

import pytest
from documents import DICO, docx_exemple, modifier_partie, pdf_exemple

from obfuscation import cli


@pytest.fixture
def espace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("Le Projet Héron, piloté par Novaltis.\n", encoding="utf-8")
    (tmp_path / "docs" / "Proposition Novaltis.docx").write_bytes(docx_exemple())
    (tmp_path / "dico.yaml").write_text(DICO, encoding="utf-8")
    return tmp_path


def obfusquer(espace, sortie=None, table=None):
    return cli.main_obfusquer([
        str(espace / "docs"),
        "-d", str(espace / "dico.yaml"),
        "-t", str(table or espace / "client.table.json"),
        "-o", str(sortie or espace / "sortie"),
    ])


def test_obfusque_un_dossier_puis_restaure(espace):
    assert obfusquer(espace) == 0
    sortie = espace / "sortie"
    assert sorted(p.name for p in sortie.iterdir()) == ["Proposition [CLIENT_1].docx", "note.md"]
    assert (sortie / "note.md").read_text(encoding="utf-8") == "Le [PROJET_1], piloté par [CLIENT_1].\n"
    table = json.loads((espace / "client.table.json").read_text(encoding="utf-8"))
    assert table["jetons"]["[CLIENT_1]"] == "Novaltis"
    code = cli.main_restaurer([str(sortie), "-t", str(espace / "client.table.json"), "-o", str(espace / "restaure")])
    assert code == 0
    assert (espace / "restaure" / "note.md").read_text(encoding="utf-8") == "Le Projet Héron, piloté par Novaltis.\n"
    assert (espace / "restaure" / "Proposition Novaltis.docx").exists()


def test_table_dans_la_sortie_refusee(espace):
    assert obfusquer(espace, table=espace / "sortie" / "client.table.json") == 2
    assert not (espace / "sortie").exists()


def test_dictionnaire_invalide(espace, capsys):
    (espace / "dico.yaml").write_text("client:\n  - x\n", encoding="utf-8")
    assert obfusquer(espace) == 2
    assert "catégorie invalide" in capsys.readouterr().err


def test_fichier_ignore_et_fichier_corrompu(espace, capsys):
    (espace / "docs" / "image.png").write_bytes(b"\x89PNG")
    (espace / "docs" / "casse.docx").write_bytes(b"pas une archive")
    assert obfusquer(espace) == 1
    erreurs = capsys.readouterr().err
    assert "image.png : format non pris en charge, ignoré" in erreurs
    assert "casse.docx : document Office illisible" in erreurs
    assert (espace / "sortie" / "note.md").exists()


def test_fuite_detectee_et_fichier_marque(espace, capsys):
    def ajouter_champ(xml):
        champ = b'<w:p><w:fldSimple w:instr="HYPERLINK https://novaltis.fr"/></w:p>'
        return xml.replace(b"<w:sectPr", champ + b"<w:sectPr", 1)

    (espace / "docs" / "Proposition Novaltis.docx").write_bytes(
        modifier_partie(docx_exemple(), "word/document.xml", ajouter_champ)
    )
    assert obfusquer(espace) == 1
    assert (espace / "sortie" / "NON-CONFORME_Proposition [CLIENT_1].docx").exists()
    assert "word/document.xml : « novaltis »" in capsys.readouterr().err


def test_pdf_converti_et_collision(espace, capsys):
    (espace / "docs" / "cahier.pdf").write_bytes(pdf_exemple("<p>Cahier des charges du Projet Héron</p>"))
    (espace / "docs" / "note.pdf").write_bytes(pdf_exemple("<p>Doublon</p>"))
    assert obfusquer(espace) == 1
    assert "[PROJET_1]" in (espace / "sortie" / "cahier.md").read_text(encoding="utf-8")
    assert "déjà produit" in capsys.readouterr().err


def test_sortie_dans_la_source_non_retraitee(espace):
    sortie = espace / "docs" / "sortie"
    assert obfusquer(espace, sortie=sortie) == 0
    assert obfusquer(espace, sortie=sortie) == 0
    assert not (sortie / "sortie").exists()


def test_interruption_table_deja_sauvegardee(espace, monkeypatch):
    appels = []
    original = cli._transformer

    def transformer(source, moteur, sens):
        appels.append(source)
        if len(appels) == 2:
            raise KeyboardInterrupt
        return original(source, moteur, sens)

    monkeypatch.setattr(cli, "_transformer", transformer)
    with pytest.raises(KeyboardInterrupt):
        obfusquer(espace)
    table = json.loads((espace / "client.table.json").read_text(encoding="utf-8"))
    assert "[CLIENT_1]" in table["jetons"] and "[PROJET_1]" in table["jetons"]


def test_restaurer_entree_standard(espace, monkeypatch, capsys):
    obfusquer(espace)
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO("**[CLIENT_1]** et \\[PROJET_1\\] et [CLIENT_9]"))
    assert cli.main_restaurer(["-", "-t", str(espace / "client.table.json")]) == 0
    resultat = capsys.readouterr()
    assert resultat.out == "**Novaltis** et Projet Héron et [CLIENT_9]"
    assert "[CLIENT_9]" in resultat.err


def test_restaurer_sans_sortie_refuse(espace):
    with pytest.raises(SystemExit) as erreur:
        cli.main_restaurer([str(espace / "docs"), "-t", str(espace / "client.table.json")])
    assert erreur.value.code == 2


def test_restaurer_table_introuvable(espace):
    assert cli.main_restaurer(["-", "-t", str(espace / "absente.table.json")]) == 2
```

- [ ] **Step 2: Vérifier l'échec**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'cli'`

- [ ] **Step 3: Implémenter**

`obfuscation/src/obfuscation/cli.py` :

```python
"""Commandes obfusquer et restaurer."""
import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from .controle import Controle
from .dictionnaire import Dictionnaire, charger_dictionnaires
from .erreurs import ErreurConfiguration, ErreurFichier, ErreurTable
from .formats import Resultat
from .formats.ooxml import EXTENSIONS_OOXML, transformer_ooxml
from .formats.pdf import pdf_vers_markdown
from .formats.texte import transformer_texte
from .moteur import Moteur, Sens
from .table import Table

SUCCES, ECHEC_FICHIERS, ECHEC_CONFIGURATION = 0, 1, 2
EXTENSIONS_TEXTE = {".md", ".txt"}
PREFIXE_NON_CONFORME = "NON-CONFORME_"


def _signaler(niveau: str, message: str) -> None:
    print(f"{niveau} : {message}", file=sys.stderr)


def _fichiers(chemins: list[Path], sortie: Path) -> Iterator[tuple[Path, Path]]:
    """(source, chemin relatif dans la sortie). Le dossier de sortie et les verrous Office (~$…) sont ignorés."""
    sortie = sortie.resolve()
    for chemin in chemins:
        if chemin.is_dir():
            for fichier in sorted(chemin.rglob("*")):
                if fichier.is_file() and not fichier.name.startswith("~$") and not fichier.resolve().is_relative_to(sortie):
                    yield fichier, fichier.relative_to(chemin)
        else:
            yield chemin, Path(chemin.name)


def _transformer_chemin(relatif: Path, moteur: Moteur, sens: Sens) -> Path:
    """Les noms de fichiers et de dossiers peuvent eux aussi contenir des termes sensibles."""
    return Path(*(moteur.transformer(partie, sens) for partie in relatif.parts))


def _transformer(source: Path, moteur: Moteur, sens: Sens) -> Resultat:
    donnees = source.read_bytes()
    extension = source.suffix.lower()
    if extension in EXTENSIONS_OOXML:
        return transformer_ooxml(donnees, moteur, sens, str(source))
    if extension == ".pdf":
        donnees = pdf_vers_markdown(donnees, str(source)).encode("utf-8")
    return transformer_texte(donnees, moteur, sens, str(source))


def _fuites(resultat: Resultat, extension: str, moteur: Moteur) -> list[str]:
    controle = Controle(moteur.dictionnaire, moteur.table)
    if extension in EXTENSIONS_OOXML:
        return controle.controler_ooxml(resultat.donnees)
    return controle.controler_texte(resultat.donnees)


def _signaler_moteur(source: object, moteur: Moteur) -> None:
    for jeton in sorted(moteur.inconnus):
        _signaler("avertissement", f"{source} : jeton absent de la table, laissé tel quel : {jeton}")
    for message in moteur.avertissements:
        _signaler("avertissement", f"{source} : {message}")
    moteur.inconnus.clear()
    moteur.avertissements.clear()


def _traiter(chemins: list[Path], sortie: Path, moteur: Moteur, sens: Sens, extensions: set[str], table: Path | None = None) -> int:
    code = SUCCES
    produits: set[Path] = set()
    for source, relatif in _fichiers(chemins, sortie):
        extension = source.suffix.lower()
        if extension not in extensions:
            _signaler("avertissement", f"{source} : format non pris en charge, ignoré")
            continue
        cible = sortie / _transformer_chemin(relatif, moteur, sens)
        if extension == ".pdf":
            cible = cible.with_suffix(".md")
        if cible in produits:
            _signaler("erreur", f"{source} : {cible} est déjà produit par un autre fichier")
            code = ECHEC_FICHIERS
            continue
        try:
            resultat = _transformer(source, moteur, sens)
        except ErreurFichier as e:
            _signaler("erreur", str(e))
            code = ECHEC_FICHIERS
            continue
        except OSError as e:
            _signaler("erreur", f"{source} : lecture impossible ({e.strerror or e})")
            code = ECHEC_FICHIERS
            continue
        produits.add(cible)
        if sens == "obfusquer":
            # La table est enregistrée avant le document : une interruption ne laisse aucun jeton orphelin.
            moteur.table.sauvegarder(table)
            fuites = _fuites(resultat, extension, moteur)
            if fuites:
                cible = cible.with_name(PREFIXE_NON_CONFORME + cible.name)
                code = ECHEC_FICHIERS
                for fuite in fuites:
                    _signaler("erreur", f"{cible} : terme sensible restant, {fuite}")
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(resultat.donnees)
        for message in resultat.avertissements:
            _signaler("avertissement", message)
        _signaler_moteur(source, moteur)
    return code


def main_obfusquer(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="obfusquer", description="Remplace les termes sensibles de documents par des jetons, avant de les confier à Claude."
    )
    parseur.add_argument("chemins", nargs="+", type=Path, help="fichiers ou dossiers à obfusquer")
    parseur.add_argument("-d", "--dictionnaire", action="append", required=True, type=Path, help="dictionnaire YAML (option répétable)")
    parseur.add_argument("-t", "--table", required=True, type=Path, help="table de correspondance, créée ou complétée")
    parseur.add_argument("-o", "--sortie", required=True, type=Path, help="dossier des documents obfusqués")
    args = parseur.parse_args(argv)
    try:
        if args.table.resolve().is_relative_to(args.sortie.resolve()):
            raise ErreurTable(f"{args.table} : la table ne doit pas être dans le dossier de sortie, elle partirait avec les documents")
        moteur = Moteur(charger_dictionnaires(args.dictionnaire), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    code = _traiter(args.chemins, args.sortie, moteur, "obfusquer", EXTENSIONS_OOXML | EXTENSIONS_TEXTE | {".pdf"}, args.table)
    moteur.table.sauvegarder(args.table)
    print(f"Table de correspondance : {args.table} ({len(moteur.table.jetons)} jetons). Elle ne doit jamais quitter cette machine.", file=sys.stderr)
    return code


def main_restaurer(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="restaurer", description="Remet les termes réels à la place des jetons.")
    parseur.add_argument("chemins", nargs="+", help="fichiers ou dossiers à restaurer, ou - pour l'entrée standard")
    parseur.add_argument("-t", "--table", required=True, type=Path, help="table de correspondance")
    parseur.add_argument("-o", "--sortie", type=Path, help="dossier des documents restaurés (inutile avec -)")
    args = parseur.parse_args(argv)
    entree_standard = args.chemins == ["-"]
    if not entree_standard and args.sortie is None:
        parseur.error("-o/--sortie est obligatoire, sauf pour l'entrée standard (-)")
    try:
        if not args.table.exists():
            raise ErreurTable(f"{args.table} : table introuvable")
        moteur = Moteur(Dictionnaire(), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    if entree_standard:
        sys.stdout.write(moteur.transformer(sys.stdin.read(), "restaurer"))
        _signaler_moteur("entrée standard", moteur)
        return SUCCES
    return _traiter([Path(c) for c in args.chemins], args.sortie, moteur, "restaurer", EXTENSIONS_OOXML | EXTENSIONS_TEXTE)
```

- [ ] **Step 4: Vérifier le succès**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Vérifier les points d'entrée**

Run: `uv run obfusquer --help && uv run restaurer --help`
Expected: aide en français des deux commandes, code 0.

- [ ] **Step 6: Lancer toute la suite**

Run: `uv run pytest`
Expected: tous les tests passent (environ 100).

- [ ] **Step 7: Commit**

```bash
git add obfuscation/src/obfuscation/cli.py obfuscation/tests/test_cli.py
git commit -m "feat(obfuscation): ajoute les commandes obfusquer et restaurer"
```

---

### Task 12: Exemples, README et intégration au dépôt

**Files:**
- Create: `obfuscation/exemples/dictionnaire.yaml`, `obfuscation/exemples/generer.py`
- Modify: `obfuscation/README.md`, `CLAUDE.md` (racine)

**Interfaces:**
- Consumes: commandes `obfusquer` / `restaurer` (tâche 11) ; corpus fictif `local-llm/n8n/exemples/sow-exemple.md` et `local-llm/n8n/exemples/Proposition – Projet Héron, v2.md`.
- Produces: `exemples/generes/` (ignoré par git) contenant un `.docx`, un `.xlsx`, un `.pptx` et un `.pdf`.

- [ ] **Step 1: Dictionnaire d'exemple**

`obfuscation/exemples/dictionnaire.yaml` :

```yaml
# Dictionnaire du corpus fictif de local-llm/n8n/exemples/ (Projet Héron).
# Une entrée = un terme, ou une liste de variantes qui partagent le même jeton ;
# la première variante est celle que « restaurer » remet en place.
CLIENT:
  - [Acme Défense, Acme Defense, Acme]
PRESTATAIRE:
  - Novaltis
PROJET:
  - [Projet Héron, Héron, Heron]
PERSONNE:
  - Jeanne Martin
motifs:
  CONTRAT: 'CTR-\d{4}-\d{4}'
```

- [ ] **Step 2: Générateur de documents d'exemple**

`obfuscation/exemples/generer.py` :

```python
"""Produit des documents Office et PDF à partir du corpus fictif de local-llm/n8n/exemples/.

Usage (depuis obfuscation/) : uv run python exemples/generer.py
"""
import html
from pathlib import Path

import openpyxl
import pymupdf
from docx import Document
from pptx import Presentation

ICI = Path(__file__).parent
CORPUS = ICI.parents[1] / "local-llm" / "n8n" / "exemples"
SORTIE = ICI / "generes"
COORDONNEES = (
    "Contrat n° CTR-2026-0042. SIRET de Novaltis : 123 456 782 00010. "
    "Contact : Jeanne Martin, jeanne.martin@novaltis.example, 01 23 45 67 89."
)


def lignes(nom: str) -> list[str]:
    return [ligne.replace("**", "") for ligne in (CORPUS / nom).read_text(encoding="utf-8").splitlines() if ligne.strip()]


def generer_docx(source: list[str]) -> None:
    document = Document()
    for ligne in source:
        if ligne.startswith("#"):
            niveau = len(ligne) - len(ligne.lstrip("#"))
            document.add_heading(ligne.lstrip("# "), level=niveau)
        else:
            document.add_paragraph(ligne)
    document.add_paragraph(COORDONNEES)
    document.sections[0].header.paragraphs[0].text = "Novaltis – Confidentiel"
    document.core_properties.author = "Jeanne Martin"
    document.save(SORTIE / "Proposition Novaltis – Projet Héron.docx")


def generer_xlsx(source: list[str]) -> None:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Acme Défense"
    feuille.append(["Exigence", "Libellé"])
    for ligne in source:
        if ligne.startswith("- EX-"):
            identifiant, _, libelle = ligne[2:].partition(" – ")
            feuille.append([identifiant, libelle])
    feuille.append(["SIRET prestataire", 12345678200010])
    feuille.oddHeader.center.text = "Projet Héron – Acme Défense"
    classeur.properties.creator = "Jeanne Martin"
    classeur.save(SORTIE / "Exigences Acme Défense.xlsx")


def generer_pptx(source: list[str]) -> None:
    presentation = Presentation()
    titre = presentation.slides.add_slide(presentation.slide_layouts[0])
    titre.shapes.title.text = "Projet Héron – lancement"
    titre.placeholders[1].text = "Novaltis pour Acme Défense"
    for ligne in source:
        if ligne.startswith("## "):
            diapo = presentation.slides.add_slide(presentation.slide_layouts[1])
            diapo.shapes.title.text = ligne[3:]
        elif not ligne.startswith("#") and len(presentation.slides) > 1:
            diapo.placeholders[1].text = ligne
            diapo.notes_slide.notes_text_frame.text = "Point à valider avec Jeanne Martin."
    presentation.core_properties.author = "Jeanne Martin"
    presentation.save(SORTIE / "Projet Héron – lancement.pptx")


def generer_pdf(source: list[str]) -> None:
    morceaux = []
    for ligne in source:
        texte = html.escape(ligne.lstrip("#- ").strip())
        morceaux.append(f"<h2>{texte}</h2>" if ligne.startswith("#") else f"<p>{texte}</p>")
    morceaux.append(f"<p>{html.escape(COORDONNEES)}</p>")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 800), "".join(morceaux), scale_low=0)
    document.set_metadata({"author": "Jeanne Martin", "title": "Cahier des charges – Projet Héron"})
    document.save(SORTIE / "Cahier des charges Projet Héron.pdf")


def main() -> None:
    SORTIE.mkdir(exist_ok=True)
    proposition = lignes("Proposition – Projet Héron, v2.md")
    cahier = lignes("sow-exemple.md")
    generer_docx(proposition)
    generer_xlsx(cahier)
    generer_pptx(proposition)
    generer_pdf(cahier)
    print(f"Documents écrits dans {SORTIE}")


if __name__ == "__main__":
    main()
```

Run: `uv run python exemples/generer.py && ls exemples/generes`
Expected: quatre fichiers (`.docx`, `.xlsx`, `.pptx`, `.pdf`).

- [ ] **Step 3: Démonstration de bout en bout**

Run :

```bash
uv run obfusquer exemples/generes -d exemples/dictionnaire.yaml -t ~/.obfuscation/heron.table.json -o sortie
ls sortie && grep -ril "novaltis\|acme\|héron\|jeanne" sortie || echo "aucun terme en clair"
```

Expected : quatre fichiers aux noms obfusqués (`Proposition [PRESTATAIRE_1] – [PROJET_1].docx`, `Exigences [CLIENT_1].xlsx`, `[PROJET_1] – lancement.pptx`, `Cahier des charges [PROJET_1].md`), code 0, avertissement éventuel sur les images, et « aucun terme en clair » (`grep` ne lit pas l'intérieur des zip : ouvrir aussi le `.docx` produit avec LibreOffice ou Word et vérifier visuellement l'en-tête, le corps et les propriétés).

Puis :

```bash
cd sortie && claude -p "Compare le cahier des charges et la proposition : liste les exigences non couvertes ou modifiées." > ../synthese.md; cd ..
uv run restaurer synthese.md -t ~/.obfuscation/heron.table.json -o restaure && cat restaure/synthese.md
```

Expected : `synthese.md` ne contient que des jetons ; `restaure/synthese.md` contient « Novaltis », « Acme Défense », « Projet Héron ». Noter la commande `claude -p` exacte qui a fonctionné (outils autorisés éventuels) et la reporter telle quelle dans le README. Supprimer ensuite `sortie/`, `restaure/`, `synthese.md` et `~/.obfuscation/heron.table.json`.

- [ ] **Step 4: README complet**

Remplacer `obfuscation/README.md` par :

````markdown
# Obfuscation de documents

Remplace les termes sensibles de documents Word, Excel, PowerPoint, PDF et texte par des jetons (`[CLIENT_1]`,
`[EMAIL_2]`…) avant de les confier à Claude, puis remet les termes réels dans les réponses. Tout se passe en local :
la table de correspondance entre jetons et termes ne quitte jamais la machine.

## Installation

```bash
cd obfuscation
uv sync
```

## Utilisation

```bash
# Obfusquer un dossier (ou des fichiers) : .docx, .xlsx, .pptx, .pdf, .md, .txt
uv run obfusquer documents/ -d mon-client.yaml -t ~/.obfuscation/mon-client.table.json -o sortie/

# Restaurer une réponse de Claude (fichier ou dossier)
uv run restaurer reponse.md -t ~/.obfuscation/mon-client.table.json -o restaure/

# Restaurer du texte collé (entrée standard → sortie standard)
uv run restaurer - -t ~/.obfuscation/mon-client.table.json < reponse.txt
```

- `-d` est répétable : plusieurs dictionnaires sont fusionnés.
- La table est créée au premier passage puis complétée : un même terme garde le même jeton d'un document et d'une
  exécution à l'autre. Une table par client ou par projet.
- Les noms de fichiers et de dossiers sont obfusqués eux aussi (`Proposition Novaltis.docx` →
  `Proposition [CLIENT_1].docx`).
- Un PDF devient un fichier Markdown (`contrat.pdf` → `contrat.md`) : la mise en page est perdue, le texte est
  conservé.
- Codes de retour : `0` succès, `1` au moins un fichier en erreur ou non conforme, `2` erreur de configuration.

## Dictionnaires

```yaml
CLIENT:
  - [Novaltis, Novaltis SA, NVL]   # variantes : même jeton ; « restaurer » remet la première
PROJET:
  - [Projet Héron, Héron, Heron]   # déclarer les variantes sans accent
PERSONNE:
  - Jeanne Martin
motifs:                            # facultatif : expressions régulières propres au contexte
  CONTRAT: 'CTR-\d{6}'
```

- Catégories en majuscules (`A-Z`, chiffres, `_`). Un même terme ne peut pas figurer dans deux catégories.
- La recherche ignore la casse, accepte n'importe quelles espaces entre les mots et ne reconnaît que des mots
  entiers (`NVL` ne touche pas `NVLX`).
- Quand deux correspondances se chevauchent, la plus longue l'emporte.

Motifs intégrés, toujours actifs : `EMAIL`, `URL`, `TELEPHONE`, `IBAN` (clé vérifiée), `SIRET` et `SIREN`
(clé de Luhn vérifiée), `IP`.

## Ce qui est traité

- **Word** : corps, tableaux, en-têtes et pieds de page, notes, commentaires, zones de texte, texte supprimé des
  révisions, noms des relecteurs, textes de remplacement des images, liens externes.
- **Excel** : cellules, commentaires, en-têtes et pieds de page, noms de feuilles (jeton sans crochets, interdits
  dans un nom de feuille : `CLIENT_1`) et formules qui les citent, nombres qui sont des SIRET ou des téléphones.
- **PowerPoint** : diapositives, notes, masques et dispositions, graphiques.
- **Partout** : métadonnées (auteur, titre, société…), documents incorporés (un classeur dans un document Word, les
  données d'un graphique). La miniature d'aperçu, qui montre la première page en clair, est supprimée.

Après chaque obfuscation, un **contrôle** relit le fichier produit, indépendamment des règles ci-dessus, et y
cherche tous les termes des dictionnaires et toutes les valeurs de la table. Si un terme subsiste, le fichier est
préfixé `NON-CONFORME_`, les emplacements sont listés et la commande renvoie `1` : ne pas l'envoyer.

## Limites

- Le texte contenu dans les **images** n'est pas traité (un avertissement indique leur nombre).
- Les **objets incorporés binaires** (OLE `.bin`) ne sont pas traités : avertissement, et le contrôle y cherche
  quand même les termes.
- Pas d'**OCR** : un PDF scanné, sans couche texte, est refusé.
- Formats anciens (`.doc`, `.xls`, `.ppt`) non pris en charge : les enregistrer d'abord au format actuel.
- Le dictionnaire ne trouve que ce qu'il contient : relire les documents obfusqués avant de les envoyer.
- **Licence** : la conversion PDF repose sur PyMuPDF, sous licence AGPL. Usage interne sans contrainte ; à
  vérifier avant toute redistribution de l'outil.

## Bonnes pratiques

- Ranger les tables **hors du dossier de travail** de Claude Code (par exemple `~/.obfuscation/`) et en interdire
  la lecture dans `.claude/settings.json` :

  ```json
  { "permissions": { "deny": ["Read(~/.obfuscation/**)"] } }
  ```

- L'outil refuse d'écrire la table dans le dossier de sortie. Les fichiers `*.table.json` sont exclus de git.
- Ne donner à Claude que le dossier de sortie.

## Démonstration avec le corpus fictif

```bash
uv run python exemples/generer.py      # documents Office et PDF tirés de local-llm/n8n/exemples/
uv run obfusquer exemples/generes -d exemples/dictionnaire.yaml -t ~/.obfuscation/heron.table.json -o sortie
cd sortie && claude -p "Compare le cahier des charges et la proposition : liste les exigences non couvertes ou modifiées." > ../synthese.md; cd ..
uv run restaurer synthese.md -t ~/.obfuscation/heron.table.json -o restaure
```

`synthese.md` ne contient que des jetons ; `restaure/synthese.md` contient les vrais noms.

## Développement

```bash
uv run pytest
```

Les documents de test sont fabriqués par `tests/documents.py` : aucun fichier binaire n'est versionné.
Conception : `docs/specs/2026-10-08-obfuscation-design.md`.
````

Si la commande `claude -p` a dû être adaptée au Step 3, reporter la version qui a fonctionné dans les sections « Démonstration » du README.

- [ ] **Step 5: CLAUDE.md racine**

Dans `CLAUDE.md` (racine) :

- section « Contenu », après la ligne `mcp/`, ajouter :
  `- \`obfuscation/\` : outil Python (uv) d'obfuscation réversible de documents Word, Excel, PowerPoint et PDF par dictionnaires, avant envoi à Claude (\`obfusquer\` / \`restaurer\`).`
- section « Commandes », ajouter :
  `- Obfuscation : \`cd obfuscation && uv sync && uv run pytest\``
- section « Règles », dans la liste « Ne jamais versionner… », ajouter `*.table.json` et `obfuscation/exemples/generes/`.

- [ ] **Step 6: Vérifications finales**

Run: `uv run pytest && git -C .. status --short`
Expected: tous les tests passent ; `git status` ne montre ni `.venv`, ni `exemples/generes/`, ni `sortie/`, ni table.

- [ ] **Step 7: Commit**

```bash
git add obfuscation/exemples/dictionnaire.yaml obfuscation/exemples/generer.py obfuscation/README.md CLAUDE.md
git commit -m "docs(obfuscation): ajoute le README, les exemples et la démonstration"
```
