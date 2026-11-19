import pytest
from documents import pdf_exemple

from obfuscation.erreurs import ErreurFichier
from obfuscation.formats.pdf import pdf_vers_markdown
from obfuscation.formats.texte import transformer_texte


def test_texte_aller_retour_fins_de_ligne_conservees(moteur):
    original = "Le Projet Héron\r\nNovaltis\r\n".encode("utf-8")
    obfusque = transformer_texte(original, moteur, "obfusquer").donnees
    assert obfusque == "Le [PROJET_1]\r\n[CLIENT_1]\r\n".encode("utf-8")
    assert transformer_texte(obfusque, moteur, "restaurer").donnees == original


def test_texte_avec_bom(moteur):
    assert transformer_texte("﻿NVL".encode("utf-8"), moteur, "obfusquer").donnees == b"[CLIENT_1]"


def test_texte_non_utf8_refuse(moteur):
    with pytest.raises(ErreurFichier, match="UTF-8"):
        transformer_texte("Héron".encode("latin-1"), moteur, "obfusquer", "note.txt")


def test_pdf_vers_markdown():
    markdown = pdf_vers_markdown(pdf_exemple("<h1>Projet Héron</h1><p>Contact : jeanne.martin@novaltis.example</p>"))
    assert "Projet Héron" in markdown and "jeanne.martin@novaltis.example" in markdown


def test_pdf_sans_texte_refuse():
    with pytest.raises(ErreurFichier, match="OCR"):
        pdf_vers_markdown(pdf_exemple(), "scan.pdf")


def test_pdf_corrompu_refuse():
    with pytest.raises(ErreurFichier, match="PDF illisible"):
        pdf_vers_markdown(b"pas un pdf", "casse.pdf")
