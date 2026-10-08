"""Documents Office (docx, xlsx, pptx) : des archives zip de parties XML."""
from lxml import etree

EXTENSIONS_OOXML = {".docx", ".xlsx", ".pptx"}
EXTENSIONS_XML = {".xml", ".rels", ".vml"}
EXTENSIONS_IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff", ".emf", ".wmf", ".svg"}
PARSEUR = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def lire_xml(contenu: bytes) -> etree._Element:
    return etree.fromstring(contenu, PARSEUR)
