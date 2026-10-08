from documents import zip_de

from obfuscation.controle import Controle
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
