import io
import zipfile

import openpyxl
import pytest
from docx import Document
from documents import ajouter_partie, docx_exemple, modifier_partie, pptx_exemple, sensibles, xlsx_exemple
from pptx import Presentation

from obfuscation.erreurs import ErreurFichier
from obfuscation.formats.ooxml import transformer_ooxml


def obfusquer(donnees, moteur):
    return transformer_ooxml(donnees, moteur, "obfusquer")


def test_les_exemples_contiennent_bien_les_termes():
    assert sensibles(docx_exemple()) >= {"novaltis", "héron", "jeanne martin", "jeanne.martin"}
    assert sensibles(xlsx_exemple()) >= {"novaltis", "héron", "jeanne martin", "12345678200010"}


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_aucun_terme_ne_subsiste(moteur, fabrique):
    assert sensibles(obfusquer(fabrique(), moteur).donnees) == set()


def test_docx_mise_en_forme_conservee(moteur):
    document = Document(io.BytesIO(obfusquer(docx_exemple(), moteur).donnees))
    premier = document.paragraphs[0]
    assert premier.text == "[CLIENT_1] signe le [PROJET_1]."
    assert premier.runs[0].text == "[CLIENT_1]" and premier.runs[0].bold
    assert document.sections[0].header.paragraphs[0].text == "[CLIENT_1] – confidentiel"
    assert document.core_properties.author == "[PERSONNE_1]"


def test_docx_miniature_retiree_images_intactes(moteur):
    original = docx_exemple()
    resultat = obfusquer(original, moteur)
    avant, apres = zipfile.ZipFile(io.BytesIO(original)), zipfile.ZipFile(io.BytesIO(resultat.donnees))
    assert "docProps/thumbnail.jpeg" in avant.namelist()
    assert "docProps/thumbnail.jpeg" not in apres.namelist()
    assert b"thumbnail" not in apres.read("_rels/.rels")
    assert apres.read("word/media/image1.png") == avant.read("word/media/image1.png")
    assert any("1 image(s)" in a for a in resultat.avertissements)


def test_docx_aller_retour(moteur):
    original = docx_exemple()
    restaure = transformer_ooxml(obfusquer(original, moteur).donnees, moteur, "restaurer").donnees

    def textes(donnees):
        return [p.text for p in Document(io.BytesIO(donnees)).paragraphs]

    assert textes(restaure) == [t.replace("Novaltis SA", "Novaltis") for t in textes(original)]


def test_xlsx_feuilles_formules_cellules(moteur):
    classeur = openpyxl.load_workbook(io.BytesIO(obfusquer(xlsx_exemple(), moteur).donnees))
    assert classeur.sheetnames == ["CLIENT_1", "Calcul"]
    feuille = classeur["CLIENT_1"]
    assert feuille["A1"].value == "Client [CLIENT_1]"
    assert "[PERSONNE_1]" in feuille["A1"].comment.text
    assert feuille["A2"].value == "[SIRET_1]"
    assert feuille.oddHeader.center.text == "[CLIENT_1] confidentiel"
    assert classeur["Calcul"]["A1"].value == "=CLIENT_1!A1"
    assert classeur["Calcul"]["A2"].value == '="[CLIENT_1]"&" SA"'


def test_xlsx_aller_retour(moteur):
    restaure = transformer_ooxml(obfusquer(xlsx_exemple(), moteur).donnees, moteur, "restaurer").donnees
    classeur = openpyxl.load_workbook(io.BytesIO(restaure))
    assert classeur.sheetnames == ["Novaltis", "Calcul"]
    assert classeur["Calcul"]["A1"].value == "=Novaltis!A1"
    assert classeur["Novaltis"]["A2"].value == "12345678200010"


def test_xlsx_vml_mal_forme_recopie(moteur):
    original = ajouter_partie(xlsx_exemple(), "xl/drawings/vmlDrawing9.vml", b"<xml><br></xml>")
    resultat = zipfile.ZipFile(io.BytesIO(obfusquer(original, moteur).donnees))
    assert resultat.read("xl/drawings/vmlDrawing9.vml") == b"<xml><br></xml>"


def test_pptx_diapo_notes_et_graphique(moteur):
    presentation = Presentation(io.BytesIO(obfusquer(pptx_exemple(), moteur).donnees))
    diapo = presentation.slides[0]
    assert diapo.shapes.title.text == "[PROJET_1]"
    zone = diapo.shapes[1].text_frame.paragraphs[0]
    assert [r.text for r in zone.runs] == ["[CLIENT_1]", " pilote."]
    assert not zone.runs[0].font.bold and zone.runs[1].font.bold
    assert diapo.notes_slide.notes_text_frame.text == "Appeler [PERSONNE_1]"
    graphique = next(s for s in diapo.shapes if s.has_chart).chart
    assert list(graphique.plots[0].categories) == ["[CLIENT_1]", "Autre"]


def test_objet_ole_signale(moteur):
    original = ajouter_partie(docx_exemple(), "word/embeddings/oleObject1.bin", b"\x00\x01")
    assert any("oleObject1.bin" in a for a in obfusquer(original, moteur).avertissements)


def test_archive_invalide(moteur):
    with pytest.raises(ErreurFichier, match="illisible"):
        transformer_ooxml(b"pas une archive", moteur, "obfusquer", "casse.docx")


def test_partie_xml_invalide(moteur):
    casse = modifier_partie(docx_exemple(), "word/document.xml", lambda _xml: b"<w:document")
    with pytest.raises(ErreurFichier, match="word/document.xml"):
        transformer_ooxml(casse, moteur, "obfusquer", "casse.docx")


def test_partie_racine_des_relations_traitee(moteur):
    # « _rels/.rels » n'a pas d'extension au sens de Python (nom commençant par un point).
    original = modifier_partie(
        docx_exemple(),
        "_rels/.rels",
        lambda xml: xml.replace(b"</Relationships>", b'<Relationship Id="rId99" Type="h" Target="https://novaltis.fr" TargetMode="External"/></Relationships>'),
    )
    relations = zipfile.ZipFile(io.BytesIO(obfusquer(original, moteur).donnees)).read("_rels/.rels")
    assert b"novaltis" not in relations and b"thumbnail" not in relations
