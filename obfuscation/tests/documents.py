"""Fabrique des documents de test : aucun binaire n'est versionné."""
import io
import struct
import zipfile
import zlib
from collections.abc import Callable

import openpyxl
import pymupdf
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from lxml import etree
from openpyxl.comments import Comment
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SENSIBLES = ("novaltis", "héron", "jeanne martin", "jeanne.martin", "12345678200010", "123 456 782")

DICO = r"""
CLIENT:
  - [Novaltis, Novaltis SA, Novaltis S.A., NVL]
PROJET:
  - [Projet Héron, Héron, Heron]
PERSONNE:
  - [Jeanne Martin, J. Martin]
motifs:
  CONTRAT: 'CTR-\d{6}'
"""


def pdf_exemple(html: str | None = None) -> bytes:
    """PDF d'une page ; sans HTML, la page est vide (comme un scan sans couche texte)."""
    document = pymupdf.open()
    page = document.new_page()
    if html:
        page.insert_htmlbox(pymupdf.Rect(50, 50, 550, 800), html)
    return document.tobytes()


def zip_de(parties: dict[str, bytes]) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, contenu in parties.items():
            archive.writestr(nom, contenu)
    return tampon.getvalue()


def png_1x1() -> bytes:
    def bloc(type_: bytes, donnees: bytes) -> bytes:
        return struct.pack(">I", len(donnees)) + type_ + donnees + struct.pack(">I", zlib.crc32(type_ + donnees))

    return (
        b"\x89PNG\r\n\x1a\n"
        + bloc(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + bloc(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + bloc(b"IEND", b"")
    )


def modifier_partie(donnees: bytes, nom: str, modification: Callable[[bytes], bytes]) -> bytes:
    """Réécrit (ou ajoute) une partie d'une archive Office."""
    with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
        parties = {info.filename: archive.read(info) for info in archive.infolist()}
    parties[nom] = modification(parties.get(nom, b""))
    return zip_de(parties)


def ajouter_partie(donnees: bytes, nom: str, contenu: bytes) -> bytes:
    return modifier_partie(donnees, nom, lambda _ancien: contenu)


def _enregistrer(document) -> bytes:
    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


def _ajouter_revision(xml: bytes) -> bytes:
    revision = (
        f'<w:p xmlns:w="{W}"><w:del w:id="90" w:author="Jeanne Martin"><w:r>'
        f"<w:delText>Ancien client : Novaltis</w:delText></w:r></w:del></w:p>"
    )
    return xml.replace(b"<w:sectPr", revision.encode() + b"<w:sectPr", 1)


def xlsx_exemple() -> bytes:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Novaltis"
    feuille["A1"] = "Client Novaltis SA"
    feuille["A1"].comment = Comment("Validé par Jeanne Martin", "Jeanne Martin")
    feuille["A2"] = 12345678200010
    feuille["A3"] = "Projet Héron"
    feuille.oddHeader.center.text = "Novaltis confidentiel"
    calcul = classeur.create_sheet("Calcul")
    calcul["A1"] = "=Novaltis!A1"
    calcul["A2"] = '="Novaltis"&" SA"'
    classeur.properties.creator = "Jeanne Martin"
    return _enregistrer(classeur)


def docx_exemple() -> bytes:
    document = Document()
    paragraphe = document.add_paragraph()
    paragraphe.add_run("Nova").bold = True
    paragraphe.add_run("ltis SA signe le Projet Héron.")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Contact : jeanne.martin@novaltis.example"
    document.sections[0].header.paragraphs[0].text = "Novaltis – confidentiel"
    relu = document.add_paragraph("Relu.")
    document.add_comment(relu.runs, text="Validé par Jeanne Martin", author="Jeanne Martin", initials="JM")
    document.add_picture(io.BytesIO(png_1x1()))
    document.part.relate_to("mailto:jeanne.martin@novaltis.example", RT.HYPERLINK, is_external=True)
    document.core_properties.author = "Jeanne Martin"
    document.core_properties.title = "Proposition Novaltis"
    donnees = modifier_partie(_enregistrer(document), "word/document.xml", _ajouter_revision)
    note = f'<w:footnotes xmlns:w="{W}"><w:footnote w:id="1"><w:p><w:r><w:t>Voir Novaltis</w:t></w:r></w:p></w:footnote></w:footnotes>'
    donnees = ajouter_partie(donnees, "word/footnotes.xml", note.encode())
    return ajouter_partie(donnees, "word/embeddings/Classeur.xlsx", xlsx_exemple())


def pptx_exemple() -> bytes:
    presentation = Presentation()
    diapo = presentation.slides.add_slide(presentation.slide_layouts[5])
    diapo.shapes.title.text = "Projet Héron"
    paragraphe = diapo.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1)).text_frame.paragraphs[0]
    paragraphe.add_run().text = "Nova"
    suite = paragraphe.add_run()
    suite.text = "ltis pilote."
    suite.font.bold = True
    diapo.notes_slide.notes_text_frame.text = "Appeler Jeanne Martin"
    donnees = CategoryChartData()
    donnees.categories = ["Novaltis", "Autre"]
    donnees.add_series("Charge", (3, 5))
    diapo.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(3), Inches(4), Inches(3), donnees)
    presentation.core_properties.author = "Jeanne Martin"
    return _enregistrer(presentation)


def texte_brut(donnees: bytes) -> str:
    """Tout le contenu décompressé de l'archive, documents incorporés compris."""
    morceaux = []
    with zipfile.ZipFile(io.BytesIO(donnees)) as archive:
        for info in archive.infolist():
            contenu = archive.read(info)
            if info.filename.endswith((".docx", ".xlsx", ".pptx")):
                morceaux.append(texte_brut(contenu))
                continue
            morceaux.append(contenu.decode("utf-8", errors="ignore"))
            try:  # texte et attributs décodés : openpyxl écrit « é » sous la forme &#233;
                racine = etree.fromstring(contenu)
            except (etree.XMLSyntaxError, ValueError):
                continue
            for element in racine.iter(tag=etree.Element):
                morceaux += [element.text or "", element.tail or "", *element.attrib.values()]
    return "\n".join(morceaux)


def sensibles(donnees: bytes) -> set[str]:
    brut = texte_brut(donnees).casefold()
    return {terme for terme in SENSIBLES if terme in brut}
