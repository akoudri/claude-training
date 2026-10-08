"""Règles propres à Excel : formules, noms de feuilles, en-têtes et cellules numériques."""
import re
from dataclasses import replace

from lxml import etree

from ..moteur import Moteur, Sens, appliquer

X = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"

FORMULES = {f"{{{X}}}f", f"{{{C}}}f", f"{{{X}}}definedName"}
EN_TETES = {f"{{{X}}}{nom}" for nom in ("oddHeader", "oddFooter", "evenHeader", "evenFooter", "firstHeader", "firstFooter")}
FEUILLE = f"{{{X}}}sheet"
SOURCE_CROISE = f"{{{X}}}worksheetSource"
CATEGORIE_FEUILLE = "FEUILLE"
CELLULE = f"{{{X}}}c"
VALEUR = f"{{{X}}}v"
VALEUR_GRAPHIQUE = f"{{{C}}}v"

# Référence à une feuille dans une formule : 'Nom avec espaces'!A1 ou Nom!A1
REFERENCE_FEUILLE = re.compile(r"'(?:[^']|'')+'(?=!)|[^\W\d][\w.]*(?=!)")
NOM_SIMPLE = re.compile(r"[^\W\d][\w.]*")
# Codes de mise en forme des en-têtes : &C, &"Arial,Gras", &12, &K00FF00, &&…
CODE_EN_TETE = re.compile(r'&(?:"[^"]*"|\d+|K[0-9A-Fa-f]{6}|.)', re.DOTALL)
CARACTERES_INTERDITS_FEUILLE = set("[]:*?/\\")
LONGUEUR_MAX_FEUILLE = 31


def nom_de_feuille(nom: str, moteur: Moteur, sens: Sens) -> str:
    """Les crochets sont interdits dans un nom de feuille : on y écrit le jeton nu (CLIENT_1)."""
    if sens == "obfusquer":
        obfusque = appliquer(nom, [replace(r, texte=r.jeton) for r in moteur.remplacements(nom, sens)])
        if len(obfusque) > LONGUEUR_MAX_FEUILLE:
            # Trop long pour Excel : le nom entier devient un seul jeton, qui le restaurera tel quel.
            return moteur.table.jeton_pour(CATEGORIE_FEUILLE, nom)[1:-1]
        return obfusque
    restaure = moteur.transformer(nom, sens)
    if not restaure or len(restaure) > LONGUEUR_MAX_FEUILLE or CARACTERES_INTERDITS_FEUILLE & set(restaure):
        moteur.avertissements.append(f"nom de feuille « {nom} » laissé tel quel : « {restaure} » n'est pas un nom de feuille valide")
        return nom
    return restaure


def traiter_nom_de_feuille(element: etree._Element, moteur: Moteur, sens: Sens, attribut: str = "name") -> bool:
    nom = element.get(attribut)
    if nom is None:
        return False
    nouveau = nom_de_feuille(nom, moteur, sens)
    if nouveau == nom:
        return False
    element.set(attribut, nouveau)
    return True


def _citer(nom: str) -> str:
    return "'" + nom.replace("'", "''") + "'"


def traiter_formule(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Les références de feuilles suivent la règle des noms de feuilles ; le reste, la règle générale."""
    texte = element.text or ""
    morceaux, curseur = [], 0
    for m in REFERENCE_FEUILLE.finditer(texte):
        morceaux.append(moteur.transformer(texte[curseur:m.start()], sens))
        reference = m.group()
        citee = reference.startswith("'")
        nom = nom_de_feuille(reference[1:-1].replace("''", "'") if citee else reference, moteur, sens)
        morceaux.append(_citer(nom) if citee or not NOM_SIMPLE.fullmatch(nom) else nom)
        curseur = m.end()
    morceaux.append(moteur.transformer(texte[curseur:], sens))
    nouveau = "".join(morceaux)
    if nouveau == texte:
        return False
    element.text = nouveau
    return True


def traiter_en_tete(element: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    texte = element.text or ""
    morceaux, curseur = [], 0
    for m in CODE_EN_TETE.finditer(texte):
        morceaux += [moteur.transformer(texte[curseur:m.start()], sens), m.group()]
        curseur = m.end()
    morceaux.append(moteur.transformer(texte[curseur:], sens))
    nouveau = "".join(morceaux)
    if nouveau == texte:
        return False
    element.text = nouveau
    return True


def traiter_cellule_numerique(cellule: etree._Element, moteur: Moteur, sens: Sens) -> bool:
    """Un nombre qui est un SIRET, un SIREN ou un téléphone devient une chaîne obfusquée.

    Pour une formule, seul le résultat mis en cache est retiré : Excel le recalcule à l'ouverture.
    """
    if sens != "obfusquer" or cellule.get("t", "n") != "n":
        return False
    valeur = cellule.find(VALEUR)
    if valeur is None or not (valeur.text or "").isdigit():
        return False
    remplacements = moteur.remplacements(valeur.text, sens)
    if not remplacements:
        return False
    if cellule.find(f"{{{X}}}f") is not None:
        cellule.remove(valeur)
        return True
    texte = appliquer(valeur.text, remplacements)
    cellule.set("t", "inlineStr")
    cellule.remove(valeur)
    chaine = etree.SubElement(cellule, f"{{{X}}}is")
    etree.SubElement(chaine, f"{{{X}}}t").text = texte
    return True


def texte_exclu(element: etree._Element) -> bool:
    """Valeurs qui ne sont pas du texte : nombres, index de chaînes partagées, caches numériques de graphiques."""
    if element.tag == VALEUR:
        parent = element.getparent()
        return parent is None or parent.get("t") != "str"
    if element.tag == VALEUR_GRAPHIQUE:
        return any(etree.QName(a).localname in ("numCache", "numLit") for a in element.iterancestors())
    return False
