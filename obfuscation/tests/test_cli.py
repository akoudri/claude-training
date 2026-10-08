import io
import json

import pytest
from documents import DICO, docx_exemple, modifier_partie, pdf_exemple

from obfuscation import cli


@pytest.fixture
def espace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("Le Projet Héron, piloté par Novaltis.\n", encoding="utf-8")
    (tmp_path / "docs" / "Proposition Novaltis.docx").write_bytes(docx_exemple())
    (tmp_path / "dico.yaml").write_text(DICO, encoding="utf-8")
    return tmp_path


def obfusquer(espace, sortie=None, table=None):
    return cli.main_obfusquer([
        str(espace / "docs"),
        "-d", str(espace / "dico.yaml"),
        "-t", str(table or espace / "client.table.json"),
        "-o", str(sortie or espace / "sortie"),
    ])


def test_obfusque_un_dossier_puis_restaure(espace):
    assert obfusquer(espace) == 0
    sortie = espace / "sortie"
    assert sorted(p.name for p in sortie.iterdir()) == ["Proposition [CLIENT_1].docx", "note.md"]
    assert (sortie / "note.md").read_text(encoding="utf-8") == "Le [PROJET_1], piloté par [CLIENT_1].\n"
    table = json.loads((espace / "client.table.json").read_text(encoding="utf-8"))
    assert table["jetons"]["[CLIENT_1]"] == "Novaltis"
    code = cli.main_restaurer([str(sortie), "-t", str(espace / "client.table.json"), "-o", str(espace / "restaure")])
    assert code == 0
    assert (espace / "restaure" / "note.md").read_text(encoding="utf-8") == "Le Projet Héron, piloté par Novaltis.\n"
    assert (espace / "restaure" / "Proposition Novaltis.docx").exists()


def test_table_dans_la_sortie_refusee(espace):
    assert obfusquer(espace, table=espace / "sortie" / "client.table.json") == 2
    assert not (espace / "sortie").exists()


def test_dictionnaire_invalide(espace, capsys):
    (espace / "dico.yaml").write_text("client:\n  - x\n", encoding="utf-8")
    assert obfusquer(espace) == 2
    assert "catégorie invalide" in capsys.readouterr().err


def test_fichier_ignore_et_fichier_corrompu(espace, capsys):
    (espace / "docs" / "image.png").write_bytes(b"\x89PNG")
    (espace / "docs" / "casse.docx").write_bytes(b"pas une archive")
    assert obfusquer(espace) == 1
    erreurs = capsys.readouterr().err
    assert "image.png : format non pris en charge, ignoré" in erreurs
    assert "casse.docx : document Office illisible" in erreurs
    assert (espace / "sortie" / "note.md").exists()


def test_fuite_detectee_et_fichier_marque(espace, capsys):
    def ajouter_etiquette(xml):
        # Identifiant technique d'un contrôle de contenu : aucune règle ne le traite, le contrôle doit le voir.
        etiquette = b'<w:sdt><w:sdtPr><w:tag w:val="Novaltis"/></w:sdtPr></w:sdt>'
        return xml.replace(b"<w:sectPr", etiquette + b"<w:sectPr", 1)

    (espace / "docs" / "Proposition Novaltis.docx").write_bytes(
        modifier_partie(docx_exemple(), "word/document.xml", ajouter_etiquette)
    )
    assert obfusquer(espace) == 1
    assert (espace / "sortie" / "NON-CONFORME_Proposition [CLIENT_1].docx").exists()
    assert "word/document.xml : « Novaltis »" in capsys.readouterr().err


def test_pdf_converti_et_collision(espace, capsys):
    (espace / "docs" / "cahier.pdf").write_bytes(pdf_exemple("<p>Cahier des charges du Projet Héron</p>"))
    (espace / "docs" / "note.pdf").write_bytes(pdf_exemple("<p>Doublon</p>"))
    assert obfusquer(espace) == 1
    assert "[PROJET_1]" in (espace / "sortie" / "cahier.md").read_text(encoding="utf-8")
    assert "déjà produit" in capsys.readouterr().err


def test_sortie_dans_la_source_non_retraitee(espace):
    sortie = espace / "docs" / "sortie"
    assert obfusquer(espace, sortie=sortie) == 0
    assert obfusquer(espace, sortie=sortie) == 0
    assert not (sortie / "sortie").exists()


def test_interruption_table_deja_sauvegardee(espace, monkeypatch):
    appels = []
    original = cli._transformer

    def transformer(source, moteur, sens):
        appels.append(source)
        if len(appels) == 2:
            raise KeyboardInterrupt
        return original(source, moteur, sens)

    monkeypatch.setattr(cli, "_transformer", transformer)
    with pytest.raises(KeyboardInterrupt):
        obfusquer(espace)
    table = json.loads((espace / "client.table.json").read_text(encoding="utf-8"))
    assert "[CLIENT_1]" in table["jetons"] and "[PROJET_1]" in table["jetons"]


def test_restaurer_entree_standard(espace, monkeypatch, capsys):
    obfusquer(espace)
    capsys.readouterr()
    monkeypatch.setattr("sys.stdin", io.StringIO("**[CLIENT_1]** et \\[PROJET_1\\] et [CLIENT_9]"))
    assert cli.main_restaurer(["-", "-t", str(espace / "client.table.json")]) == 0
    resultat = capsys.readouterr()
    assert resultat.out == "**Novaltis** et Projet Héron et [CLIENT_9]"
    assert "[CLIENT_9]" in resultat.err


def test_restaurer_sans_sortie_refuse(espace):
    with pytest.raises(SystemExit) as erreur:
        cli.main_restaurer([str(espace / "docs"), "-t", str(espace / "client.table.json")])
    assert erreur.value.code == 2


def test_restaurer_table_introuvable(espace):
    assert cli.main_restaurer(["-", "-t", str(espace / "absente.table.json")]) == 2
