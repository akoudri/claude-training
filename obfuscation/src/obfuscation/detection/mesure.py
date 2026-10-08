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
