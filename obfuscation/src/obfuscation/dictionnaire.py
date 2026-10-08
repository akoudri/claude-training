"""Dictionnaires YAML : catégories de termes sensibles et motifs propres au contexte."""
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import yaml

from .erreurs import ErreurDictionnaire

CATEGORIE = re.compile(r"[A-Z][A-Z0-9_]*")
CLE_MOTIFS = "motifs"


# Un terme est délimité par tout ce qui n'est pas une lettre : « Novaltis_2026 », « dossier_Novaltis » ou
# « Novaltis2026 » le contiennent, mais pas « Novaltisien ».
AVANT = r"(?<![^\W\d_])"
APRES = r"(?![^\W\d_])"
# Word remplace « ' » par « ’ » et peut insérer des tirets insécables : ces variantes sont équivalentes.
APOSTROPHES = "'’‘ʼ"
TIRETS = "-‐‑‒–"
EQUIVALENTS = {c: f"[{APOSTROPHES}]" for c in APOSTROPHES} | {c: f"[{re.escape(TIRETS)}]" for c in TIRETS}
VERS_ASCII = str.maketrans({**{c: "'" for c in APOSTROPHES}, **{c: "-" for c in TIRETS}})


def normaliser(texte: str) -> str:
    """Forme de comparaison : accents composés (NFC), apostrophes et tirets ASCII, espaces réduites, casse ignorée."""
    return unicodedata.normalize("NFC", " ".join(texte.split())).translate(VERS_ASCII).casefold()


def _motif_de_mot(mot: str) -> str:
    return "".join(EQUIVALENTS.get(c) or re.escape(c) for c in mot)


def motif_de_terme(terme: str) -> str:
    """Regex d'un terme : toute suite d'espaces (insécables comprises) est acceptée entre ses mots.

    Les accents peuvent être composés (« é ») ou décomposés (« e » + accent combinant, fréquent sous macOS) ;
    apostrophes et tirets typographiques valent leur forme ASCII.
    """
    formes = dict.fromkeys(unicodedata.normalize(forme, terme) for forme in ("NFC", "NFD"))
    motifs = [r"\s+".join(_motif_de_mot(mot) for mot in forme.split()) for forme in formes]
    return motifs[0] if len(motifs) == 1 else "(?:" + "|".join(motifs) + ")"


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
        terme = self.termes.get(normaliser(trouve))
        if terme is None:
            # re.IGNORECASE et casefold() divergent sur quelques lettres (« İ », « ſ »…) : la regex de chaque
            # variante tranche, pour que tout ce que la recherche a trouvé soit bien remplacé.
            for variante in self.variantes:
                if re.fullmatch(motif_de_terme(variante), trouve, re.IGNORECASE):
                    return self.termes[normaliser(variante)]
        return terme

    @cached_property
    def recherche(self) -> re.Pattern | None:
        """À chaque position, la plus longue variante qui y commence ; le groupe 1 est la variante trouvée.

        Le lookahead rend les correspondances chevauchantes : le moteur choisit ensuite la plus longue.
        """
        if not self.variantes:
            return None
        alternatives = "|".join(motif_de_terme(v) for v in sorted(self.variantes, key=len, reverse=True))
        return re.compile(rf"(?={AVANT}({alternatives}){APRES})", re.IGNORECASE)


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
