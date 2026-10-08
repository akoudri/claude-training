"""Commandes obfusquer, restaurer et detecter."""
import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from .controle import Controle
from .detection import CATEGORIES_PAR_DEFAUT, MODELE_PAR_DEFAUT, URL_PAR_DEFAUT, analyser
from .detection.ollama import ClientOllama, ErreurOllama
from .detection.sortie import ecrire, rendre
from .dictionnaire import CATEGORIE, Dictionnaire, charger_dictionnaires
from .erreurs import ErreurConfiguration, ErreurFichier, ErreurTable
from .extraction import extraire
from .formats import Resultat
from .formats.fichier import EXTENSIONS_LISIBLES, EXTENSIONS_TEXTE, transformer_fichier
from .formats.ooxml import EXTENSIONS_OOXML
from .moteur import Moteur, Sens
from .table import Table

SUCCES, ECHEC_FICHIERS, ECHEC_CONFIGURATION = 0, 1, 2
PREFIXE_NON_CONFORME = "NON-CONFORME_"


def _signaler(niveau: str, message: str) -> None:
    print(f"{niveau} : {message}", file=sys.stderr)


def _fichiers(chemins: list[Path], sortie: Path) -> Iterator[tuple[Path, Path]]:
    """(source, chemin relatif dans la sortie). Le dossier de sortie et les verrous Office (~$…) sont ignorés."""
    sortie = sortie.resolve()
    for chemin in chemins:
        if chemin.is_dir():
            for fichier in sorted(chemin.rglob("*")):
                if fichier.is_file() and not fichier.name.startswith("~$") and not fichier.resolve().is_relative_to(sortie):
                    yield fichier, fichier.relative_to(chemin)
        else:
            yield chemin, Path(chemin.name)


def _verifier_sortie(chemins: list[Path], sortie: Path) -> None:
    """Les fichiers placés dans le dossier de sortie sont ignorés : une sortie qui contient les sources ne traiterait rien."""
    for chemin in chemins:
        if chemin.resolve().is_relative_to(sortie.resolve()):
            raise ErreurConfiguration(f"{sortie} : le dossier de sortie contient les documents sources ({chemin})")


def _transformer_chemin(relatif: Path, moteur: Moteur, sens: Sens) -> Path:
    """Les noms de fichiers et de dossiers peuvent eux aussi contenir des termes sensibles."""
    return Path(*(moteur.transformer(partie, sens) for partie in relatif.parts))


def _fuites(resultat: Resultat, extension: str, relatif: Path, moteur: Moteur) -> list[str]:
    controle = Controle(moteur.dictionnaire, moteur.table)
    nom = str(relatif)
    fuites = [f"nom du fichier : « {terme} »" for terme in sorted(controle.chercher(nom) | controle.chercher_motifs(nom))]
    if extension in EXTENSIONS_OOXML:
        return fuites + controle.controler_ooxml(resultat.donnees)
    return fuites + controle.controler_texte(resultat.donnees)


def _signaler_moteur(source: object, moteur: Moteur) -> None:
    for jeton in sorted(moteur.inconnus):
        _signaler("avertissement", f"{source} : jeton absent de la table, laissé tel quel : {jeton}")
    for message in moteur.avertissements:
        _signaler("avertissement", f"{source} : {message}")
    moteur.inconnus.clear()
    moteur.avertissements.clear()


def _traiter(chemins: list[Path], sortie: Path, moteur: Moteur, sens: Sens, extensions: set[str], table: Path | None = None) -> int:
    code = SUCCES
    produits: set[Path] = set()
    for source, relatif in _fichiers(chemins, sortie):
        extension = source.suffix.lower()
        if extension not in extensions:
            _signaler("avertissement", f"{source} : format non pris en charge, ignoré")
            continue
        cible = sortie / _transformer_chemin(relatif, moteur, sens)
        if extension == ".pdf":
            cible = cible.with_suffix(".md")
        if cible in produits:
            _signaler("erreur", f"{source} : {cible} est déjà produit par un autre fichier")
            code = ECHEC_FICHIERS
            continue
        try:
            resultat = transformer_fichier(source, moteur, sens)
        except ErreurFichier as e:
            _signaler("erreur", str(e))
            code = ECHEC_FICHIERS
            continue
        except OSError as e:
            _signaler("erreur", f"{source} : lecture impossible ({e.strerror or e})")
            code = ECHEC_FICHIERS
            continue
        produits.add(cible)
        if sens == "obfusquer":
            # La table est enregistrée avant le document : une interruption ne laisse aucun jeton orphelin.
            moteur.table.sauvegarder(table)
            fuites = _fuites(resultat, extension, cible.relative_to(sortie), moteur)
            non_conforme = cible.with_name(PREFIXE_NON_CONFORME + cible.name)
            # Une version d'une exécution précédente ne doit pas rester à côté (surtout une version sans préfixe).
            (cible if fuites else non_conforme).unlink(missing_ok=True)
            if fuites:
                cible = non_conforme
                code = ECHEC_FICHIERS
                for fuite in fuites:
                    _signaler("erreur", f"{cible} : terme sensible restant, {fuite}")
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(resultat.donnees)
        for message in resultat.avertissements:
            _signaler("avertissement", message)
        _signaler_moteur(source, moteur)
    return code


def main_obfusquer(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="obfusquer", description="Remplace les termes sensibles de documents par des jetons, avant de les confier à Claude."
    )
    parseur.add_argument("chemins", nargs="+", type=Path, help="fichiers ou dossiers à obfusquer")
    parseur.add_argument("-d", "--dictionnaire", action="append", required=True, type=Path, help="dictionnaire YAML (option répétable)")
    parseur.add_argument("-t", "--table", required=True, type=Path, help="table de correspondance, créée ou complétée")
    parseur.add_argument("-o", "--sortie", required=True, type=Path, help="dossier des documents obfusqués")
    args = parseur.parse_args(argv)
    try:
        if args.table.resolve().is_relative_to(args.sortie.resolve()):
            raise ErreurTable(f"{args.table} : la table ne doit pas être dans le dossier de sortie, elle partirait avec les documents")
        _verifier_sortie(args.chemins, args.sortie)
        moteur = Moteur(charger_dictionnaires(args.dictionnaire), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    code = _traiter(args.chemins, args.sortie, moteur, "obfusquer", EXTENSIONS_LISIBLES, args.table)
    moteur.table.sauvegarder(args.table)
    print(f"Table de correspondance : {args.table} ({len(moteur.table.jetons)} jetons). Elle ne doit jamais quitter cette machine.", file=sys.stderr)
    return code


def main_restaurer(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="restaurer", description="Remet les termes réels à la place des jetons.")
    parseur.add_argument("chemins", nargs="+", help="fichiers ou dossiers à restaurer, ou - pour l'entrée standard")
    parseur.add_argument("-t", "--table", required=True, type=Path, help="table de correspondance")
    parseur.add_argument("-o", "--sortie", type=Path, help="dossier des documents restaurés (inutile avec -)")
    args = parseur.parse_args(argv)
    entree_standard = args.chemins == ["-"]
    if not entree_standard and args.sortie is None:
        parseur.error("-o/--sortie est obligatoire, sauf pour l'entrée standard (-)")
    try:
        if not args.table.exists():
            raise ErreurTable(f"{args.table} : table introuvable")
        if not entree_standard:
            _verifier_sortie([Path(c) for c in args.chemins], args.sortie)
        moteur = Moteur(Dictionnaire(), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    if entree_standard:
        sys.stdout.write(moteur.transformer(sys.stdin.read(), "restaurer"))
        _signaler_moteur("entrée standard", moteur)
        return SUCCES
    return _traiter([Path(c) for c in args.chemins], args.sortie, moteur, "restaurer", EXTENSIONS_OOXML | EXTENSIONS_TEXTE)


def _categories(texte: str) -> list[str]:
    categories = list(dict.fromkeys(c.strip() for c in texte.split(",") if c.strip()))
    if not categories or not all(CATEGORIE.fullmatch(c) for c in categories):
        raise ErreurConfiguration(f"catégories invalides : {texte} (majuscules, chiffres et _, séparées par des virgules)")
    return categories


def main_detecter(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(
        prog="detecter",
        description="Propose un dictionnaire candidat à partir des entités repérées par un LLM local (Ollama). "
        "Rien ne quitte la machine.",
    )
    parseur.add_argument("chemins", nargs="+", type=Path, help="fichiers ou dossiers à analyser")
    parseur.add_argument("-o", "--sortie", required=True, type=Path, help="dictionnaire candidat à créer (jamais écrasé)")
    parseur.add_argument("-d", "--dictionnaire", action="append", default=[], type=Path,
                         help="dictionnaire existant, dont les termes ne sont pas reproposés (option répétable)")
    parseur.add_argument("--modele", default=MODELE_PAR_DEFAUT, help=f"modèle Ollama (défaut : {MODELE_PAR_DEFAUT})")
    parseur.add_argument("--ollama-url", default=URL_PAR_DEFAUT, help=f"serveur Ollama (défaut : {URL_PAR_DEFAUT})")
    parseur.add_argument("--categories", default=",".join(CATEGORIES_PAR_DEFAUT),
                         help="catégories recherchées, séparées par des virgules (défaut : %(default)s)")
    parseur.add_argument("--delai", type=float, default=300.0, help="délai maximal par appel au modèle, en secondes")
    args = parseur.parse_args(argv)
    try:
        categories = _categories(args.categories)
        if args.sortie.exists():
            raise ErreurConfiguration(f"{args.sortie} existe déjà : un dictionnaire candidat relu ne doit pas être écrasé")
        exclus = charger_dictionnaires(args.dictionnaire)
        client = ClientOllama(args.ollama_url, args.modele, args.delai)
        client.verifier()
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    code = SUCCES
    documents = []
    for source, relatif in _fichiers(args.chemins, args.sortie):
        if source.suffix.lower() not in EXTENSIONS_LISIBLES:
            _signaler("avertissement", f"{source} : format non pris en charge, ignoré")
            continue
        try:
            texte = extraire(source)
        except ErreurFichier as e:
            _signaler("erreur", str(e))
            code = ECHEC_FICHIERS
            continue
        except OSError as e:
            _signaler("erreur", f"{source} : lecture impossible ({e.strerror or e})")
            code = ECHEC_FICHIERS
            continue
        # Les noms de fichiers et de dossiers peuvent eux aussi contenir des termes sensibles.
        documents.append((str(relatif), "\n".join([*relatif.parts, texte])))
    try:
        bilan = analyser(documents, client, categories, exclus, _signaler)
    except ErreurOllama as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    ecrire(args.sortie, rendre(bilan.candidats, categories, args.modele, bilan.ignores))
    if bilan.ignores:
        code = ECHEC_FICHIERS
    print(
        f"Dictionnaire candidat : {args.sortie} ({len(bilan.candidats)} candidats ; {bilan.rejetees} propositions "
        f"absentes du texte, rejetées ; {len(bilan.ignores)} morceaux non analysés). À relire avant usage.",
        file=sys.stderr,
    )
    return code
