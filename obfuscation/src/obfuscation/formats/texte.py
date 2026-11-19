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
