"""Commandes obfusquer et restaurer."""
import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

from .controle import Controle
from .dictionnaire import Dictionnaire, charger_dictionnaires
from .erreurs import ErreurConfiguration, ErreurFichier, ErreurTable
from .formats import Resultat
from .formats.ooxml import EXTENSIONS_OOXML, transformer_ooxml
from .formats.pdf import pdf_vers_markdown
from .formats.texte import transformer_texte
from .moteur import Moteur, Sens
from .table import Table

SUCCES, ECHEC_FICHIERS, ECHEC_CONFIGURATION = 0, 1, 2
EXTENSIONS_TEXTE = {".md", ".txt"}
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


def _transformer_chemin(relatif: Path, moteur: Moteur, sens: Sens) -> Path:
    """Les noms de fichiers et de dossiers peuvent eux aussi contenir des termes sensibles."""
    return Path(*(moteur.transformer(partie, sens) for partie in relatif.parts))


def _transformer(source: Path, moteur: Moteur, sens: Sens) -> Resultat:
    donnees = source.read_bytes()
    extension = source.suffix.lower()
    if extension in EXTENSIONS_OOXML:
        return transformer_ooxml(donnees, moteur, sens, str(source))
    if extension == ".pdf":
        donnees = pdf_vers_markdown(donnees, str(source)).encode("utf-8")
    return transformer_texte(donnees, moteur, sens, str(source))


def _fuites(resultat: Resultat, extension: str, moteur: Moteur) -> list[str]:
    controle = Controle(moteur.dictionnaire, moteur.table)
    if extension in EXTENSIONS_OOXML:
        return controle.controler_ooxml(resultat.donnees)
    return controle.controler_texte(resultat.donnees)


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
            resultat = _transformer(source, moteur, sens)
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
            fuites = _fuites(resultat, extension, moteur)
            if fuites:
                cible = cible.with_name(PREFIXE_NON_CONFORME + cible.name)
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
        moteur = Moteur(charger_dictionnaires(args.dictionnaire), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    code = _traiter(args.chemins, args.sortie, moteur, "obfusquer", EXTENSIONS_OOXML | EXTENSIONS_TEXTE | {".pdf"}, args.table)
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
        moteur = Moteur(Dictionnaire(), Table.charger(args.table))
    except ErreurConfiguration as e:
        _signaler("erreur", str(e))
        return ECHEC_CONFIGURATION
    if entree_standard:
        sys.stdout.write(moteur.transformer(sys.stdin.read(), "restaurer"))
        _signaler_moteur("entrée standard", moteur)
        return SUCCES
    return _traiter([Path(c) for c in args.chemins], args.sortie, moteur, "restaurer", EXTENSIONS_OOXML | EXTENSIONS_TEXTE)
