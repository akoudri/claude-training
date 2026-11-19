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
