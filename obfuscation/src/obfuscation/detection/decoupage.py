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
