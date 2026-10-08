import pytest
from documents import docx_exemple, pptx_exemple, xlsx_exemple, zip_de

from obfuscation.controle import Controle
from obfuscation.formats.ooxml import transformer_ooxml
from obfuscation.table import Table

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def test_texte_propre_et_texte_avec_fuite(dictionnaire):
    controle = Controle(dictionnaire, Table())
    assert controle.controler_texte("[CLIENT_1] signe.".encode()) == []
    assert controle.controler_texte("Signé : NOVALTIS".encode()) == ["« NOVALTIS »"]


def test_valeurs_de_la_table_recherchees(dictionnaire):
    table = Table()
    table.jeton_pour("EMAIL", "contact@acme.example")
    assert Controle(dictionnaire, table).controler_texte(b"ecrire a contact@acme.example") == ["« contact@acme.example »"]


def test_terme_dans_un_attribut_non_traite(dictionnaire):
    document = zip_de({
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:p><w:fldSimple w:instr="HYPERLINK https://novaltis.fr"/>'
        f"</w:p></w:document>".encode(),
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["word/document.xml : « novaltis »"]


def test_terme_coupe_entre_segments(dictionnaire):
    document = zip_de({
        "word/document.xml": f'<w:document xmlns:w="{W}"><w:p><w:r><w:t>Nova</w:t></w:r><w:r><w:t>ltis</w:t>'
        f"</w:r></w:p></w:document>".encode(),
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["word/document.xml : « Novaltis »"]


def test_document_incorpore_binaire_et_image(dictionnaire):
    classeur = zip_de({"xl/sharedStrings.xml": b"<sst><si><t>H\xc3\xa9ron</t></si></sst>"})
    document = zip_de({
        "word/embeddings/Classeur.xlsx": classeur,
        "word/embeddings/oleObject1.bin": b"  " + "Novaltis".encode("utf-16-le"),
        "word/media/image1.png": b"\x89PNG Novaltis",
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == [
        "word/embeddings/Classeur.xlsx › xl/sharedStrings.xml : « Héron »",
        "word/embeddings/oleObject1.bin : « Novaltis »",
    ]


def test_xml_mal_forme_avec_references_de_caracteres(dictionnaire):
    document = zip_de({"xl/drawings/vmlDrawing1.vml": b"<xml><br>Projet H&#233;ron</xml>"})
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["xl/drawings/vmlDrawing1.vml : « Projet Héron »"]


def test_accents_decomposes_detectes(dictionnaire):
    assert Controle(dictionnaire, Table()).controler_texte("Projet Héron".encode()) == ["« Projet Héron »"]


def test_image_svg_analysee(dictionnaire):
    document = zip_de({"word/media/logo.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><text>Novaltis</text></svg>'})
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["word/media/logo.svg : « Novaltis »"]


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_documents_obfusques_conformes(moteur, fabrique):
    donnees = transformer_ooxml(fabrique(), moteur, "obfusquer").donnees
    assert Controle(moteur.dictionnaire, moteur.table).controler_ooxml(donnees) == []


@pytest.mark.parametrize("fabrique", [docx_exemple, xlsx_exemple, pptx_exemple])
def test_documents_originaux_non_conformes(moteur, fabrique):
    assert Controle(moteur.dictionnaire, moteur.table).controler_ooxml(fabrique()) != []


def test_paquet_incorpore_reconnu_par_son_contenu(dictionnaire):
    classeur = zip_de({"[Content_Types].xml": b"<Types/>", "xl/sharedStrings.xml": b"<sst><si><t>Novaltis</t></si></sst>"})
    document = zip_de({"word/embeddings/Feuille.xlsm": classeur})
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == [
        "word/embeddings/Feuille.xlsm › xl/sharedStrings.xml : « Novaltis »"
    ]


def test_image_vectorielle_et_image_mal_nommee_analysees(dictionnaire):
    document = zip_de({
        "word/media/image2.emf": b"\x01\x00\x00\x00" + "Novaltis".encode("utf-16-le"),
        "word/media/image3.png": b"texte Novaltis",
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == [
        "word/media/image2.emf : « Novaltis »",
        "word/media/image3.png : « Novaltis »",
    ]


def test_motifs_recherches_meme_hors_table(dictionnaire):
    document = zip_de({
        "word/document.xml": f'<w:document xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/x">'
        f'<w:sdt><w:sdtPr><w:tag w:val="paul@acme.example"/></w:sdtPr></w:sdt>'
        f"<w:instrText>Écrire au 01 23 45 67 89</w:instrText>"
        f'<w:x Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" w:id="123456782"/>'
        f"<w:v>123456782</w:v></w:document>".encode(),
    })
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == [
        "word/document.xml : « 01 23 45 67 89 »",
        "word/document.xml : « paul@acme.example »",
    ]


def test_motifs_dans_un_texte(dictionnaire):
    assert Controle(dictionnaire, Table()).controler_texte("IBAN FR76 3000 6000 0112 3456 7890 189".encode()) == [
        "« FR76 3000 6000 0112 3456 7890 189 »"
    ]


def test_nombre_sensible_hors_cellule_detecte(dictionnaire):
    # Seules les valeurs de cellules et de graphiques (« v ») sont dispensées de la recherche des motifs.
    document = zip_de({"docProps/custom.xml": b"<p><n>12345678200010</n><v>123456782</v></p>"})
    assert Controle(dictionnaire, Table()).controler_ooxml(document) == ["docProps/custom.xml : « 12345678200010 »"]
