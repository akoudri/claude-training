"""Fabrique des documents de test : aucun binaire n'est versionné."""
import io
import zipfile

import pymupdf

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
