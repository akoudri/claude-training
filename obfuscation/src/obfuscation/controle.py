"""Contrôle résiduel : relit un fichier produit et y cherche tout terme sensible, sans passer par les règles de format."""
import html
import io
import re
import zipfile

from lxml import etree

from .dictionnaire import Dictionnaire, motif_de_terme
from .formats.ooxml import est_archive, lire_xml
from .motifs import MOTIFS_INTEGRES, Motif
from .table import Table


# Images matricielles, reconnues à leur signature : leurs données compressées produiraient de faux positifs.
SIGNATURES_IMAGES = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM", b"II*\x00", b"MM\x00*")
# Dans les attributs, seuls les motifs sans faux positifs sur les valeurs techniques d'Office
# (URL de schémas, identifiants numériques) sont recherchés.
MOTIFS_ATTRIBUTS = {"EMAIL", "IBAN", "SIRET", "TELEPHONE"}
NOMBRE = re.compile(r"-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?")


class Controle:
    """Cherche les variantes des dictionnaires, toutes les valeurs déjà enregistrées dans la table, et les motifs."""

    def __init__(self, dictionnaire: Dictionnaire, table: Table):
        termes = {*dictionnaire.variantes, *table.jetons.values()}
        alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
        self._regex = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE) if termes else None
        self._motifs = [*MOTIFS_INTEGRES, *(Motif(c, r) for c, r in dictionnaire.motifs.items())]

    def chercher(self, texte: str) -> set[str]:
        if self._regex is None:
            return set()
        return {m.group() for m in self._regex.finditer(texte)}

    def chercher_motifs(self, texte: str, categories: set[str] | None = None) -> set[str]:
        return {
            m.group()
            for motif in self._motifs
            if categories is None or motif.categorie in categories
            for m in motif.regex.finditer(texte)
            if m.end() > m.start() and motif.valide(m.group())
        }

    def controler_texte(self, donnees: bytes) -> list[str]:
        texte = donnees.decode("utf-8", errors="replace")
        return [f"« {terme} »" for terme in sorted(self.chercher(texte) | self.chercher_motifs(texte))]

    def controler_ooxml(self, donnees: bytes, prefixe: str = "") -> list[str]:
        fuites = []
        with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
            for info in archive.infolist():
                contenu = archive.read(info)
                partie = prefixe + info.filename
                if est_archive(contenu):
                    try:  # document ou archive incorporés, quelle que soit leur extension
                        fuites += self.controler_ooxml(contenu, f"{partie} › ")
                        continue
                    except zipfile.BadZipFile:
                        pass
                if not contenu.startswith(SIGNATURES_IMAGES):
                    fuites += [f"{partie} : « {terme} »" for terme in sorted(self._chercher_partie(contenu))]
        return fuites

    def _chercher_partie(self, contenu: bytes) -> set[str]:
        try:
            racine = lire_xml(contenu)
        except (etree.XMLSyntaxError, ValueError):
            # Partie binaire ou XML mal formé : recherche brute, en UTF-8 et en UTF-16 (objets OLE),
            # références de caractères (&#233;) décodées.
            return self.chercher(html.unescape(contenu.decode("utf-8", errors="replace"))) | self.chercher(
                contenu.decode("utf-16-le", errors="replace")
            )
        elements = list(racine.iter(tag=etree.Element))
        trouves = set()
        for element in elements:
            for texte in (element.text, element.tail):
                if texte and texte.strip():
                    trouves |= self.chercher(texte)
                    if not (etree.QName(element).localname == "v" and NOMBRE.fullmatch(texte.strip())):
                        # Les valeurs numériques des cellules et des graphiques (« v ») sont dispensées des motifs.
                        trouves |= self.chercher_motifs(texte)
            for valeur in element.attrib.values():
                trouves |= self.chercher(valeur) | self.chercher_motifs(valeur, MOTIFS_ATTRIBUTS)
        # Un terme coupé entre deux segments n'apparaît que dans le texte mis bout à bout.
        return trouves | self.chercher("".join(e.text or "" for e in elements))
