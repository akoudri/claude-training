"""Produit des documents Office et PDF à partir du corpus fictif de local-llm/n8n/exemples/.

Usage (depuis obfuscation/) : uv run python exemples/generer.py
"""
import html
from pathlib import Path

import openpyxl
import pymupdf
from docx import Document
from pptx import Presentation

ICI = Path(__file__).parent
CORPUS = ICI.parents[1] / "local-llm" / "n8n" / "exemples"
SORTIE = ICI / "generes"
COORDONNEES = (
    "Contrat n° CTR-2026-0042. SIRET de Novaltis : 123 456 782 00010. "
    "Contact : Jeanne Martin, jeanne.martin@novaltis.example, 01 23 45 67 89."
)


def lignes(nom: str) -> list[str]:
    return [ligne.replace("**", "") for ligne in (CORPUS / nom).read_text(encoding="utf-8").splitlines() if ligne.strip()]


def generer_docx(source: list[str]) -> None:
    document = Document()
    for ligne in source:
        if ligne.startswith("#"):
            niveau = len(ligne) - len(ligne.lstrip("#"))
            document.add_heading(ligne.lstrip("# "), level=niveau)
        else:
            document.add_paragraph(ligne)
    document.add_paragraph(COORDONNEES)
    document.sections[0].header.paragraphs[0].text = "Novaltis – Confidentiel"
    document.core_properties.author = "Jeanne Martin"
    document.save(SORTIE / "Proposition Novaltis – Projet Héron.docx")


def generer_xlsx(source: list[str]) -> None:
    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "Acme Défense"
    feuille.append(["Exigence", "Libellé"])
    for ligne in source:
        if ligne.startswith("- EX-"):
            identifiant, _, libelle = ligne[2:].partition(" – ")
            feuille.append([identifiant, libelle])
    feuille.append(["SIRET prestataire", 12345678200010])
    feuille.oddHeader.center.text = "Projet Héron – Acme Défense"
    classeur.properties.creator = "Jeanne Martin"
    classeur.save(SORTIE / "Exigences Acme Défense.xlsx")


def generer_pptx(source: list[str]) -> None:
    presentation = Presentation()
    titre = presentation.slides.add_slide(presentation.slide_layouts[0])
    titre.shapes.title.text = "Projet Héron – lancement"
    titre.placeholders[1].text = "Novaltis pour Acme Défense"
    for ligne in source:
        if ligne.startswith("## "):
            diapo = presentation.slides.add_slide(presentation.slide_layouts[1])
            diapo.shapes.title.text = ligne[3:]
        elif not ligne.startswith("#") and len(presentation.slides) > 1:
            diapo.placeholders[1].text = ligne
            diapo.notes_slide.notes_text_frame.text = "Point à valider avec Jeanne Martin."
    presentation.core_properties.author = "Jeanne Martin"
    presentation.save(SORTIE / "Projet Héron – lancement.pptx")


def generer_pdf(source: list[str]) -> None:
    morceaux = []
    for ligne in source:
        texte = html.escape(ligne.lstrip("#- ").strip())
        morceaux.append(f"<h2>{texte}</h2>" if ligne.startswith("#") else f"<p>{texte}</p>")
    morceaux.append(f"<p>{html.escape(COORDONNEES)}</p>")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_htmlbox(pymupdf.Rect(50, 50, 545, 800), "".join(morceaux), scale_low=0)
    document.set_metadata({"author": "Jeanne Martin", "title": "Cahier des charges – Projet Héron"})
    document.save(SORTIE / "Cahier des charges Projet Héron.pdf")


def main() -> None:
    SORTIE.mkdir(exist_ok=True)
    proposition = lignes("Proposition – Projet Héron, v2.md")
    cahier = lignes("sow-exemple.md")
    generer_docx(proposition)
    generer_xlsx(cahier)
    generer_pptx(proposition)
    generer_pdf(cahier)
    print(f"Documents écrits dans {SORTIE}")


if __name__ == "__main__":
    main()
