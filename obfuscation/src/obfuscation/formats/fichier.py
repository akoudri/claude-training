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
