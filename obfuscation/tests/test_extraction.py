import pytest
from documents import docx_exemple, pdf_exemple, pptx_exemple, xlsx_exemple

from obfuscation.erreurs import ErreurFichier
from obfuscation.extraction import extraire


def test_extrait_le_texte_d_un_docx_sans_le_modifier(tmp_path):
    chemin = tmp_path / "proposition.docx"
    chemin.write_bytes(docx_exemple())
    avant = chemin.read_bytes()
    texte = extraire(chemin)
    assert "Novaltis SA signe le Projet Héron." in texte  # segments de mise en forme réunis
    assert "Voir Novaltis" in texte  # note de bas de page
    assert "Novaltis – confidentiel" in texte  # en-tête
    assert "Validé par Jeanne Martin" in texte  # commentaire
    assert chemin.read_bytes() == avant


def test_extrait_cellules_commentaires_et_noms_de_feuilles(tmp_path):
    chemin = tmp_path / "classeur.xlsx"
    chemin.write_bytes(xlsx_exemple())
    lignes = extraire(chemin).splitlines()
    assert "Client Novaltis SA" in lignes
    assert "Novaltis" in lignes  # nom de la feuille
    assert "Validé par Jeanne Martin" in lignes


def test_extrait_diapositives_et_notes(tmp_path):
    chemin = tmp_path / "lancement.pptx"
    chemin.write_bytes(pptx_exemple())
    texte = extraire(chemin)
    assert "Novaltis pilote." in texte
    assert "Appeler Jeanne Martin" in texte


def test_extrait_un_pdf_et_un_texte(tmp_path):
    pdf = tmp_path / "contrat.pdf"
    pdf.write_bytes(pdf_exemple("<p>Contrat signé avec Novaltis.</p>"))
    assert "Novaltis" in extraire(pdf)
    note = tmp_path / "note.md"
    note.write_text("Le Projet Héron.\n", encoding="utf-8")
    assert extraire(note) == "Le Projet Héron.\n"


def test_fichier_illisible(tmp_path):
    chemin = tmp_path / "casse.docx"
    chemin.write_bytes(b"pas une archive")
    with pytest.raises(ErreurFichier):
        extraire(chemin)
