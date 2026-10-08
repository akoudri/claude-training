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


def _ligne(texte: str) -> str:
    """Texte placé dans un commentaire : sur une seule ligne. Un saut de ligne (nom de fichier, contexte) sortirait
    du commentaire et injecterait des entrées dans le dictionnaire."""
    return " ".join(texte.split())


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
        morceaux.append(f"{_pluriel(n, 'variante')} {_pluriel(n, 'présumée')}, à vérifier : {_ligne(', '.join(candidat.presumees))}")
    if candidat.autres_categories:
        morceaux.append(f"aussi proposé en {_ligne(', '.join(candidat.autres_categories))}")
    return " ; ".join(morceaux)


def rendre(candidats: list[Candidat], categories: list[str], modele: str, ignores: list[str], jour: date | None = None) -> str:
    lignes = [
        f"# Dictionnaire candidat produit par « detecter » le {(jour or date.today()).isoformat()} (modèle {_ligne(modele)}).",
        "# À relire : supprimer les lignes refusées, corriger les catégories. Rien n'est appliqué sans « obfusquer ».",
        f"# Morceaux non analysés : {_ligne(', '.join(ignores)) if ignores else 'aucun'}.",
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
                lignes.append(f"    # « {_ligne(candidat.contexte)} »")
    return "\n".join(lignes) + "\n"


def ecrire(chemin: Path, contenu: str) -> None:
    """Création exclusive : un candidat déjà relu n'est jamais écrasé. Le fichier est ensuite relu comme le ferait
    « obfusquer » ; un échec ici est un défaut de « rendre », et le fichier est laissé en place pour l'examiner."""
    with chemin.open("x", encoding="utf-8") as fichier:
        fichier.write(contenu)
    charger_dictionnaires([chemin])
