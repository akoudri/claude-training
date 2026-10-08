"""Contrôle résiduel : relit un fichier produit et y cherche tout terme sensible, sans passer par les règles de format."""
import html
import io
import re
import zipfile

from lxml import etree

from .dictionnaire import APRES, AVANT, Dictionnaire, motif_de_terme
from .formats.ooxml import est_archive, lire_xml
from .motifs import MOTIFS_INTEGRES, Motif
from .table import Table


# Images matricielles, reconnues à leur signature : leurs données compressées produiraient de faux positifs.
SIGNATURES_IMAGES = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM", b"II*\x00", b"MM\x00*")
# Dans les attributs, seuls les motifs sans faux positifs sur les valeurs techniques d'Office
# (URL de schémas, identifiants numériques) sont recherchés.
MOTIFS_ATTRIBUTS = {"EMAIL", "IBAN", "SIRET", "TELEPHONE"}
# Caractères invisibles qui peuvent couper un terme (césure conditionnelle, espaces de largeur nulle).
INVISIBLES = str.maketrans("", "", "\u00ad\u200b\u200c\u200d\u2060\ufeff")
# Éléments Word sans texte qui valent un caractère dans le texte affiché.
LITTERAUX = {"tab": "\t", "br": "\n", "cr": "\n", "noBreakHyphen": "-", "softHyphen": ""}
NOMBRE = re.compile(r"-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?")


class Controle:
    """Cherche les variantes des dictionnaires, toutes les valeurs déjà enregistrées dans la table, et les motifs."""

    def __init__(self, dictionnaire: Dictionnaire, table: Table):
        termes = {*dictionnaire.variantes, *table.jetons.values()}
        alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
        self._regex = re.compile(rf"{AVANT}(?:{alternatives}){APRES}", re.IGNORECASE) if termes else None
        self._motifs = [*MOTIFS_INTEGRES, *(Motif(c, r) for c, r in dictionnaire.motifs.items())]
        # Les motifs déclarés par l'utilisateur sont toujours recherchés, attributs compris.
        self._motifs_attributs = MOTIFS_ATTRIBUTS | set(dictionnaire.motifs)

    def chercher(self, texte: str) -> set[str]:
        if self._regex is None:
            return set()
        visible = texte.translate(INVISIBLES)
        return {m.group() for t in {texte, visible} for m in self._regex.finditer(t)}

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
            # Partie binaire ou XML mal formé : recherche brute en UTF-8 (références &#233; décodées), en UTF-16 et
            # en cp1252 (objets OLE).
            return self._chercher_brut(contenu) | {
                terme for codage in ("utf-16-le", "cp1252") for terme in self.chercher(contenu.decode(codage, errors="replace"))
            }
        # Filet de sécurité : le texte brut couvre aussi commentaires, instructions de traitement et DOCTYPE.
        trouves = self._chercher_brut(contenu)
        elements = list(racine.iter(tag=etree.Element))
        for element in elements:
            for texte in (element.text, element.tail):
                if texte and texte.strip():
                    trouves |= self.chercher(texte)
                    if not (etree.QName(element).localname == "v" and NOMBRE.fullmatch(texte.strip())):
                        # Les valeurs numériques des cellules et des graphiques (« v ») sont dispensées des motifs.
                        trouves |= self.chercher_motifs(texte)
            for valeur in element.attrib.values():
                trouves |= self.chercher(valeur) | self.chercher_motifs(valeur, self._motifs_attributs)
        # Un terme coupé entre deux segments n'apparaît que dans le texte mis bout à bout.
        bout_a_bout = "".join(e.text or LITTERAUX.get(etree.QName(e).localname, "") for e in elements)
        return trouves | self.chercher(bout_a_bout)

    def _chercher_brut(self, contenu: bytes) -> set[str]:
        brut = html.unescape(contenu.decode("utf-8", errors="replace"))
        return self.chercher(brut) | self.chercher_motifs(brut, self._motifs_attributs)
