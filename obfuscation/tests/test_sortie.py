from datetime import date

import pytest

from obfuscation.detection.candidats import Candidat
from obfuscation.detection.sortie import ecrire, rendre
from obfuscation.dictionnaire import charger_dictionnaires


def test_yaml_commente_et_chargeable_par_obfusquer(tmp_path):
    candidats = [
        Candidat("CLIENT", ["Acme Défense", "Acme Defense"], 3, "…signé par Acme Défense pour…", ["Acme"]),
        Candidat("PERSONNE", ["Jeanne Martin"], 1, "…par Jeanne Martin…", autres_categories=["CLIENT"]),
    ]
    contenu = rendre(candidats, ["CLIENT", "PROJET", "PERSONNE"], "granite4.2:8b", [], date(2026, 10, 8))
    assert contenu.splitlines()[0] == (
        "# Dictionnaire candidat produit par « detecter » le 2026-10-08 (modèle granite4.2:8b)."
    )
    assert "# Morceaux non analysés : aucun." in contenu
    assert "  - [Acme Défense, Acme Defense, Acme]  # 3 occurrences ; variante présumée, à vérifier : Acme" in contenu
    assert "    # « …signé par Acme Défense pour… »" in contenu
    assert "  - Jeanne Martin  # 1 occurrence ; aussi proposé en CLIENT" in contenu
    assert "# PROJET : aucun candidat" in contenu
    chemin = tmp_path / "client.candidats.yaml"
    ecrire(chemin, contenu)
    dictionnaire = charger_dictionnaires([chemin])
    assert dictionnaire.terme("Acme").canonique == "Acme Défense"
    assert dictionnaire.terme("Jeanne Martin").categorie == "PERSONNE"


@pytest.mark.parametrize("terme", ["R&D: Lyon", "#Héron", "'Atlas'", "Dupont, Fils", "[Projet] X", "Dupont & Fils", "true"])
def test_caracteres_speciaux(tmp_path, terme):
    contenu = rendre([Candidat("PROJET", [terme, terme + " Bis"], 1)], ["PROJET"], "m", [])
    chemin = tmp_path / "c.candidats.yaml"
    ecrire(chemin, contenu)
    dictionnaire = charger_dictionnaires([chemin])
    assert dictionnaire.terme(terme).canonique == terme


def test_morceaux_ignores_dans_l_en_tete(tmp_path):
    contenu = rendre([], ["CLIENT"], "m", ["a.docx — morceau 2/5", "b.md — morceau 1/1"])
    assert "# Morceaux non analysés : a.docx — morceau 2/5, b.md — morceau 1/1." in contenu
    chemin = tmp_path / "vide.candidats.yaml"
    ecrire(chemin, contenu)
    assert charger_dictionnaires([chemin]).variantes == []


def test_refuse_d_ecraser(tmp_path):
    chemin = tmp_path / "relu.candidats.yaml"
    chemin.write_text("CLIENT:\n  - Novaltis\n", encoding="utf-8")
    with pytest.raises(FileExistsError):
        ecrire(chemin, rendre([], ["CLIENT"], "m", []))
    assert chemin.read_text(encoding="utf-8") == "CLIENT:\n  - Novaltis\n"


def test_un_saut_de_ligne_ne_sort_pas_des_commentaires(tmp_path):
    # Un nom de fichier peut contenir un saut de ligne : il ne doit jamais injecter d'entrée dans le YAML.
    candidat = Candidat("CLIENT", ["Novaltis"], 1, "contexte\nPROJET:\n  - Injecté", ["Nova\nPROJET:"])
    contenu = rendre(
        [candidat], ["CLIENT"], "modele\nPERSONNE:\n  - Injecté", ["piège\nLIEU:\n  - Injecté — morceau 1/1"]
    )
    chemin = tmp_path / "c.candidats.yaml"
    ecrire(chemin, contenu)
    dictionnaire = charger_dictionnaires([chemin])
    assert dictionnaire.terme("Injecté") is None
    assert all(ligne.startswith(("#", "CLIENT:", "  - ", "    # ")) for ligne in contenu.splitlines())
