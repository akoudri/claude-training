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
        retenus: list[tuple[int, int, str, str]] = []  # (debut, fin, catégorie, valeur), par priorité
        for debut, fin, _, categorie, valeur in candidats:
            chevauches = [r for r in retenus if debut < r[1] and r[0] < fin]
            if not chevauches:
                retenus.append((debut, fin, categorie, valeur))
            elif not any(r[0] <= debut and fin <= r[1] for r in chevauches):
                # Chevauchement partiel : écarter le candidat laisserait sa partie non couverte en clair.
                # On fusionne sous la catégorie prioritaire ; la valeur est le texte exact, pour un aller-retour fidèle.
                union_debut = min(debut, *(r[0] for r in chevauches))
                union_fin = max(fin, *(r[1] for r in chevauches))
                fusion = (union_debut, union_fin, chevauches[0][2], texte[union_debut:union_fin])
                retenus = [fusion if r is chevauches[0] else r for r in retenus if r is chevauches[0] or r not in chevauches]
        remplacements = []
        for debut, fin, categorie, valeur in sorted(retenus):
            jeton = self.table.jeton_pour(categorie, valeur)
            remplacements.append(Remplacement(debut, fin, jeton, jeton[1:-1]))
        return remplacements

    def _a_restaurer(self, texte: str) -> list[Remplacement]:
        for m in JETON_ENTRE_CROCHETS.finditer(texte):
            if self.table.valeur(m.group(1)) is None:
                self.inconnus.add(m.group(0))
        recherche = self._recherche_jetons()
        if recherche is None:
            return []
        remplacements = []
        for m in recherche.finditer(texte):
            jeton = m.group(1).replace("\\", "")
            remplacements.append(Remplacement(m.start(), m.end(), self.table.valeur(jeton), jeton))
        return remplacements

    def _recherche_jetons(self) -> re.Pattern | None:
        """Jetons connus, avec ou sans crochets, et tels que Markdown les reformate : crochets ou « _ » échappés
        (\\[CLIENT\\_1\\]), italique (_CLIENT_1_). Un jeton ne doit pas être collé à une lettre, à un chiffre
        ni à un « _ » lui-même collé à un mot (MY_CLIENT_1)."""
        if self._taille_table != len(self.table.jetons):
            nus = sorted((jeton[1:-1] for jeton in self.table.jetons), key=len, reverse=True)
            alternatives = "|".join(re.escape(nu).replace("_", r"\\?_") for nu in nus)
            self._jetons_connus = (
                re.compile(r"(?:\\?\[)?(?<![^\W_])(?<!\w_)(" + alternatives + r")(?![^\W_])(?!_\w)(?:\\?\])?") if nus else None
            )
            self._taille_table = len(self.table.jetons)
        return self._jetons_connus
