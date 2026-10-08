"""Remplacements dans une partie XML d'un document Office (Word, Excel, PowerPoint)."""
from lxml import etree

from ..moteur import Moteur, Sens
from ..segments import reecrire
from . import excel

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
X = excel.X
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def _q(ns: str, nom: str) -> str:
    return f"{{{ns}}}{nom}"


# Unité de texte (paragraphe, chaîne Excel, commentaire) → éléments qui portent ses segments.
UNITES = {
    _q(W, "p"): (_q(W, "t"), _q(W, "delText")),
    _q(A, "p"): (_q(A, "t"),),
    _q(X, "si"): (_q(X, "t"),),
    _q(X, "is"): (_q(X, "t"),),
    _q(X, "text"): (_q(X, "t"),),
}
SEGMENTS = {tag for tags in UNITES.values() for tag in tags}
PRESERVER_ESPACES = {_q(W, "t"), _q(W, "delText"), _q(X, "t")}
# Attributs lisibles : relecteurs, textes de remplacement des images, info-bulles, instructions de champs…
ATTRIBUTS = {"author", "initials", "descr", "title", "tooltip", "userName", "instr"}
ATTRIBUTS_PAR_ELEMENT = {
    ("alias", "val"),
    ("cNvPr", "name"),
    ("docPr", "name"),
    ("person", "displayName"),
    ("tblCaption", "val"),
    ("tblDescription", "val"),
}


def transformer_xml(racine: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Applique le moteur à une partie ; renvoie vrai si elle a changé."""
    modifie = False
    for unite in racine.iter(*UNITES):
        segments = [s for s in unite.iter(*UNITES[unite.tag]) if _unite(s) is unite]
        modifie |= _traiter_segments(segments, moteur, sens)
    # Liste figée : traiter_cellule_numerique modifie l'arbre pendant le parcours.
    for element in list(racine.iter(tag=etree.Element)):
        if element.tag in SEGMENTS and _unite(element) is not None:
            pass  # déjà traité avec son unité
        elif element.tag in excel.FORMULES:
            modifie |= excel.traiter_formule(element, moteur, sens)
        elif element.tag in excel.EN_TETES:
            modifie |= excel.traiter_en_tete(element, moteur, sens)
        elif element.tag == excel.CELLULE:
            modifie |= excel.traiter_cellule_numerique(element, moteur, sens)
        elif element.text and element.text.strip() and not excel.texte_exclu(element):
            modifie |= _traiter_texte(element, moteur, sens)
        modifie |= _traiter_attributs(element, moteur, sens)
    return modifie


def _unite(element: etree._Element) -> etree._Element | None:
    """Unité la plus proche : une zone de texte imbriquée forme sa propre unité."""
    return next(element.iterancestors(*UNITES), None)


def _traiter_segments(segments: list[etree._Element], moteur: Moteur, sens: Sens) -> bool:
    textes = [s.text or "" for s in segments]
    remplacements = moteur.remplacements("".join(textes), sens)
    if not remplacements:
        return False
    for segment, texte in zip(segments, reecrire(textes, remplacements)):
        segment.text = texte
        if segment.tag in PRESERVER_ESPACES and texte != texte.strip():
            segment.set(XML_SPACE, "preserve")
    return True


def _traiter_texte(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    nouveau = moteur.transformer(element.text, sens)
    if nouveau == element.text:
        return False
    element.text = nouveau
    return True


def _traiter_attributs(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    modifie = False
    local = etree.QName(element).localname
    for nom, valeur in element.attrib.items():
        attribut = etree.QName(nom).localname
        lien_externe = local == "Relationship" and attribut == "Target" and element.get("TargetMode") == "External"
        if attribut in ATTRIBUTS or (local, attribut) in ATTRIBUTS_PAR_ELEMENT or lien_externe:
            nouveau = moteur.transformer(valeur, sens)
            if nouveau != valeur:
                element.set(nom, nouveau)
                modifie = True
    if element.tag == excel.FEUILLE:
        modifie |= excel.traiter_nom_de_feuille(element, moteur, sens)
    return modifie
