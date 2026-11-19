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
