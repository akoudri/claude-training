"""Contrôle résiduel : relit un fichier produit et y cherche tout terme sensible, sans passer par les règles de format."""
import html
import io
import re
import zipfile

from lxml import etree

from .dictionnaire import Dictionnaire, motif_de_terme
from .formats.ooxml import EXTENSIONS_IMAGES, EXTENSIONS_OOXML, extension, lire_xml
from .table import Table


class Controle:
    """Cherche les variantes des dictionnaires et toutes les valeurs déjà enregistrées dans la table."""

    def __init__(self, dictionnaire: Dictionnaire, table: Table):
        termes = {*dictionnaire.variantes, *table.jetons.values()}
        alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
        self._regex = re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE) if termes else None

    def chercher(self, texte: str) -> set[str]:
        if self._regex is None:
            return set()
        return {m.group() for m in self._regex.finditer(texte)}

    def controler_texte(self, donnees: bytes) -> list[str]:
        return [f"« {terme} »" for terme in sorted(self.chercher(donnees.decode("utf-8", errors="replace")))]

    def controler_ooxml(self, donnees: bytes, prefixe: str = "") -> list[str]:
        fuites = []
        with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
            for info in archive.infolist():
                contenu = archive.read(info)
                partie = prefixe + info.filename
                type_partie = extension(info.filename)
                if type_partie in EXTENSIONS_OOXML:
                    fuites += self.controler_ooxml(contenu, f"{partie} › ")
                elif type_partie not in EXTENSIONS_IMAGES:
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
            for texte in (element.text, element.tail, *element.attrib.values()):
                if texte:
                    trouves |= self.chercher(texte)
        # Un terme coupé entre deux segments n'apparaît que dans le texte mis bout à bout.
        return trouves | self.chercher("".join(e.text or "" for e in elements))
