"""Documents Office (docx, xlsx, pptx) : des archives zip de parties XML."""
import io
import zipfile
from pathlib import PurePosixPath

from lxml import etree

from ..erreurs import ErreurFichier
from ..moteur import Moteur, Sens
from . import Resultat
from .xml_texte import transformer_xml

EXTENSIONS_OOXML = {".docx", ".xlsx", ".pptx"}
EXTENSIONS_XML = {".xml", ".rels", ".vml"}
EXTENSIONS_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf", ".svg"}
RELATIONS = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
TYPE_MINIATURE = "http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"
PARSEUR = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def lire_xml(contenu: bytes) -> etree._Element:
    return etree.fromstring(contenu, PARSEUR)


def extension(partie: str) -> str:
    """Extension d'une partie ; « _rels/.rels » en a une, contrairement à ce que dit PurePosixPath.suffix."""
    nom = PurePosixPath(partie).name
    return "." + nom.rsplit(".", 1)[1].lower() if "." in nom else ""


def transformer_ooxml(donnees: bytes, moteur: Moteur, sens: Sens, nom: str = "document") -> Resultat:
    """Transforme chaque partie XML ; tout le reste est recopié à l'identique, dans le même ordre."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(donnees))
    except zipfile.BadZipFile as e:
        raise ErreurFichier(f"{nom} : document Office illisible (fichier corrompu ou protégé par mot de passe)") from e
    avertissements: list[str] = []
    images = 0
    sortie = io.BytesIO()
    with archive, zipfile.ZipFile(sortie, "w") as resultat:
        # La miniature est une image de la première page : elle montrerait le texte en clair.
        miniatures = _miniatures(archive) if sens == "obfusquer" else set()
        for info in archive.infolist():
            if info.filename in miniatures:
                continue
            contenu = archive.read(info)
            type_partie = extension(info.filename)
            if type_partie in EXTENSIONS_XML:
                contenu = _transformer_partie(contenu, info.filename, moteur, sens, miniatures, nom)
            elif type_partie in EXTENSIONS_OOXML:
                incorpore = transformer_ooxml(contenu, moteur, sens, f"{nom} › {info.filename}")
                contenu = incorpore.donnees
                avertissements += incorpore.avertissements
            elif type_partie in EXTENSIONS_IMAGES:
                images += 1
            elif "/embeddings/" in info.filename and sens == "obfusquer":
                avertissements.append(f"{nom} : objet incorporé non traité ({info.filename})")
            resultat.writestr(info, contenu)
    if images and sens == "obfusquer":
        avertissements.append(f"{nom} : {images} image(s) non analysée(s) ; le texte qu'elles contiennent reste lisible")
    return Resultat(sortie.getvalue(), avertissements)


def _miniatures(archive: zipfile.ZipFile) -> set[str]:
    try:
        racine = lire_xml(archive.read("_rels/.rels"))
    except (KeyError, etree.XMLSyntaxError):
        return set()
    return {
        relation.get("Target", "").lstrip("/")
        for relation in racine.iter(f"{{{RELATIONS}}}Relationship")
        if relation.get("Type") == TYPE_MINIATURE
    }


def _transformer_partie(contenu: bytes, partie: str, moteur: Moteur, sens: Sens, miniatures: set[str], nom: str) -> bytes:
    try:
        racine = lire_xml(contenu)
    except etree.XMLSyntaxError as e:
        if partie.endswith(".vml"):
            return contenu  # VML hérité, souvent mal formé : le contrôle résiduel le vérifie en texte brut
        raise ErreurFichier(f"{nom} : partie XML illisible ({partie})") from e
    modifie = transformer_xml(racine, moteur, sens)
    if miniatures:
        modifie |= _retirer_miniatures(racine, miniatures)
    if not modifie:
        return contenu
    arbre = racine.getroottree()
    return etree.tostring(arbre, xml_declaration=True, encoding="UTF-8", standalone=arbre.docinfo.standalone)


def _retirer_miniatures(racine: etree._Element, miniatures: set[str]) -> bool:
    """Retire la relation vers la miniature et sa déclaration de type."""
    a_retirer = [r for r in racine.iter(f"{{{RELATIONS}}}Relationship") if r.get("Type") == TYPE_MINIATURE]
    a_retirer += [o for o in racine.iter(f"{{{TYPES}}}Override") if o.get("PartName", "").lstrip("/") in miniatures]
    for element in a_retirer:
        element.getparent().remove(element)
    return bool(a_retirer)
