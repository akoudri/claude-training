import pytest
from documents import DICO
from faux_ollama import reponse_chat

from obfuscation import cli
from obfuscation.dictionnaire import charger_dictionnaires


@pytest.fixture
def espace(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("Le Projet Héron, piloté par Novaltis.\n", encoding="utf-8")
    (tmp_path / "dico.yaml").write_text(DICO, encoding="utf-8")
    return tmp_path


def detecter(espace, faux_ollama, *options):
    return cli.main_detecter([
        str(espace / "docs"), "-o", str(espace / "client.candidats.yaml"), "--ollama-url", faux_ollama.url, *options,
    ])


def test_detecte_et_ecrit_un_candidat(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([
        {"terme": "Novaltis", "categorie": "PRESTATAIRE"},
        {"terme": "Projet Héron", "categorie": "PROJET"},
        {"terme": "Inventé SA", "categorie": "CLIENT"},
    ]), 0)]
    assert detecter(espace, faux_ollama) == 0
    dictionnaire = charger_dictionnaires([espace / "client.candidats.yaml"])
    assert dictionnaire.terme("Novaltis").categorie == "PRESTATAIRE"
    assert dictionnaire.terme("Projet Héron").categorie == "PROJET"
    assert dictionnaire.terme("Inventé SA") is None
    assert faux_ollama.requetes[0]["messages"][1]["content"] == "note.md\nLe Projet Héron, piloté par Novaltis."


def test_le_nom_du_fichier_est_analyse(espace, faux_ollama):
    (espace / "docs" / "note.md").unlink()
    (espace / "docs" / "Proposition Acme.md").write_text("Texte neutre.\n", encoding="utf-8")
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Acme", "categorie": "CLIENT"}]), 0)]
    assert detecter(espace, faux_ollama) == 0
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Acme").categorie == "CLIENT"


def test_exclut_les_termes_des_dictionnaires(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "CLIENT"}]), 0)]
    assert detecter(espace, faux_ollama, "-d", str(espace / "dico.yaml")) == 0
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).variantes == []


def test_refuse_une_sortie_existante(espace, faux_ollama):
    (espace / "client.candidats.yaml").write_text("CLIENT:\n  - Relu\n", encoding="utf-8")
    assert detecter(espace, faux_ollama) == 2
    assert (espace / "client.candidats.yaml").read_text(encoding="utf-8") == "CLIENT:\n  - Relu\n"
    assert faux_ollama.requetes == []


def test_ollama_injoignable(espace, capsys):
    code = cli.main_detecter([str(espace / "docs"), "-o", str(espace / "c.candidats.yaml"), "--ollama-url", "http://127.0.0.1:1"])
    assert code == 2
    assert not (espace / "c.candidats.yaml").exists()
    assert "docker compose up -d ollama" in capsys.readouterr().err


def test_modele_absent(espace, faux_ollama, capsys):
    assert detecter(espace, faux_ollama, "--modele", "autre:1b") == 2
    assert "ollama pull autre:1b" in capsys.readouterr().err


def test_categories_invalides(espace, faux_ollama):
    assert detecter(espace, faux_ollama, "--categories", "client,LIEU") == 2


def test_categories_personnalisees(espace, faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "SOCIETE"}]), 0)]
    assert detecter(espace, faux_ollama, "--categories", "SOCIETE") == 0
    assert faux_ollama.requetes[0]["format"]["properties"]["entites"]["items"]["properties"]["categorie"]["enum"] == ["SOCIETE"]
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Novaltis").categorie == "SOCIETE"


def test_morceau_non_analyse_code_1(espace, faux_ollama):
    invalide = (200, {"message": {"content": "pas du json"}}, 0)
    faux_ollama.reponses = [invalide, invalide]
    assert detecter(espace, faux_ollama) == 1
    contenu = (espace / "client.candidats.yaml").read_text(encoding="utf-8")
    assert "# Morceaux non analysés : note.md — morceau 1/1." in contenu


def test_fichier_illisible_code_1(espace, faux_ollama):
    (espace / "docs" / "casse.docx").write_bytes(b"pas une archive")
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "PRESTATAIRE"}]), 0)]
    assert detecter(espace, faux_ollama) == 1
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Novaltis") is not None


def test_dossier_de_sortie_absent(espace, faux_ollama):
    code = cli.main_detecter([str(espace / "docs"), "-o", str(espace / "absent" / "c.candidats.yaml"), "--ollama-url", faux_ollama.url])
    assert code == 2
    assert faux_ollama.requetes == []


def test_ollama_perdu_ecrit_le_candidat_partiel(espace, faux_ollama, capsys):
    (espace / "docs" / "suite.md").write_text("Acme paie.\n", encoding="utf-8")
    faux_ollama.reponses = [
        (200, reponse_chat([{"terme": "Novaltis", "categorie": "PRESTATAIRE"}]), 0),
        (404, {"error": "model not found"}, 0),
    ]
    assert detecter(espace, faux_ollama) == 2
    contenu = (espace / "client.candidats.yaml").read_text(encoding="utf-8")
    assert "suite.md — morceau 1/1" in contenu
    assert charger_dictionnaires([espace / "client.candidats.yaml"]).terme("Novaltis") is not None
    assert "ollama pull" in capsys.readouterr().err
