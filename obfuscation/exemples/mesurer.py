"""Mesure de « detecter » : rappel et précision par rapport à un dictionnaire de référence.

Usage (depuis obfuscation/, Ollama démarré) :
    uv run python exemples/generer.py                    # une fois : documents du corpus fictif Héron
    uv run python exemples/mesurer.py                    # corpus Héron, 3 exécutions
    uv run python exemples/mesurer.py documents/ --reference client.yaml   # documents réels

Seuls des chiffres sont affichés, jamais un terme ni un nom de fichier : la sortie peut être partagée sans fuite.
"""
import argparse
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from obfuscation.detection import CATEGORIES_PAR_DEFAUT, MODELE_PAR_DEFAUT, URL_PAR_DEFAUT, analyser
from obfuscation.detection.mesure import comparer
from obfuscation.detection.ollama import ClientOllama, ErreurOllama
from obfuscation.dictionnaire import Dictionnaire, charger_dictionnaires
from obfuscation.erreurs import ErreurConfiguration, ErreurFichier
from obfuscation.extraction import extraire
from obfuscation.formats.fichier import EXTENSIONS_LISIBLES

ICI = Path(__file__).parent


class Chronometre:
    """Enveloppe le client pour cumuler le temps passé sur chaque document."""

    def __init__(self, client: ClientOllama):
        self.client = client
        self.document = ""
        self.durees: Counter = Counter()

    def entites(self, texte, categories):
        debut = time.perf_counter()
        try:
            return self.client.entites(texte, categories)
        finally:
            self.durees[self.document] += time.perf_counter() - debut

    def signaler(self, niveau: str, message: str) -> None:
        if niveau == "analyse":
            self.document = message.split(" — ")[0]


def documents(dossier: Path) -> list[tuple[str, str]]:
    """(« document n », texte) : les noms réels ne sont jamais affichés."""
    fichiers = sorted(
        f for f in dossier.rglob("*")
        if f.is_file() and f.suffix.lower() in EXTENSIONS_LISIBLES and not f.name.startswith("~$")
    )
    resultat = []
    for i, fichier in enumerate(fichiers, 1):
        try:
            resultat.append((f"document {i}", "\n".join([*fichier.relative_to(dossier).parts, extraire(fichier)])))
        except (ErreurFichier, OSError):
            print(f"document {i} illisible, ignoré", file=sys.stderr)
    return resultat


def main() -> int:
    parseur = argparse.ArgumentParser(description="Mesure le rappel et la précision de « detecter ».")
    parseur.add_argument("dossier", nargs="?", type=Path, default=ICI / "generes", help="documents à analyser")
    parseur.add_argument("--reference", type=Path, default=ICI / "dictionnaire.yaml", help="dictionnaire validé")
    parseur.add_argument("--modele", default=MODELE_PAR_DEFAUT)
    parseur.add_argument("--ollama-url", default=URL_PAR_DEFAUT)
    parseur.add_argument("--executions", type=int, default=3)
    args = parseur.parse_args()
    if not args.dossier.is_dir():
        print("dossier introuvable (pour le corpus Héron : uv run python exemples/generer.py)", file=sys.stderr)
        return 2
    try:
        reference = charger_dictionnaires([args.reference])
        client = ClientOllama(args.ollama_url, args.modele)
        client.verifier()
    except (ErreurConfiguration, ErreurOllama) as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 2
    docs = documents(args.dossier)
    texte = "\n".join(t for _, t in docs)
    print(f"{len(docs)} documents, modèle {args.modele}, {args.executions} exécutions")
    scores = []
    for n in range(1, args.executions + 1):
        chrono = Chronometre(client)
        try:
            bilan = analyser(docs, chrono, CATEGORIES_PAR_DEFAUT, Dictionnaire(), chrono.signaler)
        except ErreurOllama as e:
            print(f"erreur : {e}", file=sys.stderr)
            return 2
        score = comparer(bilan.candidats, reference, texte)
        scores.append(score)
        print(
            f"Exécution {n} : rappel {score.trouvees}/{score.reference} ({score.rappel:.0%}), "
            f"catégorie juste {score.bonne_categorie}/{score.trouvees}, "
            f"précision {score.justes}/{score.candidats} ({score.precision:.0%}), "
            f"morceaux non analysés {len(bilan.ignores)}"
        )
        print("  durées : " + " ; ".join(f"{nom} {chrono.durees[nom]:.0f} s" for nom, _ in docs))
    for libelle, valeurs in (("Rappel", [s.rappel for s in scores]), ("Précision", [s.precision for s in scores])):
        print(f"{libelle} : moyenne {statistics.mean(valeurs):.0%} (min {min(valeurs):.0%}, max {max(valeurs):.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
