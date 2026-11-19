"""PDF → Markdown : la mise en page est perdue, le texte est conservé. PyMuPDF est sous licence AGPL."""
import pymupdf
import pymupdf4llm

from ..erreurs import ErreurFichier


def pdf_vers_markdown(donnees: bytes, nom: str = "document.pdf") -> str:
    try:
        document = pymupdf.open(stream=donnees, filetype="pdf")
    except RuntimeError as e:  # pymupdf.FileDataError en dérive
        raise ErreurFichier(f"{nom} : PDF illisible ({e})") from e
    with document:
        if document.needs_pass:
            raise ErreurFichier(f"{nom} : PDF protégé par mot de passe")
        if not any(page.get_text().strip() for page in document):
            raise ErreurFichier(f"{nom} : aucun texte dans ce PDF (document scanné ?) ; l'OCR n'est pas prise en charge")
        # use_ocr=False : sans cela, pymupdf4llm tente une OCR Tesseract si elle est installée.
        return pymupdf4llm.to_markdown(document, use_ocr=False, show_progress=False)
