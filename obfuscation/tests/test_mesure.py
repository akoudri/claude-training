from obfuscation.detection.candidats import Candidat
from obfuscation.detection.mesure import comparer


def test_rappel_precision_et_categorie(dictionnaire):
    # dictionnaire (conftest) : CLIENT Novaltis…, PROJET Projet Héron / Héron / Heron, PERSONNE Jeanne Martin…
    texte = "Novaltis mène le Projet Héron."  # Jeanne Martin absente : hors de la référence
    candidats = [
        Candidat("PRESTATAIRE", ["Novaltis"]),  # trouvé, mauvaise catégorie
        Candidat("PROJET", ["Projet Héron"], presumees=["Héron"]),  # trouvé
        Candidat("LIEU", ["Lyon"]),  # fausse alerte
    ]
    score = comparer(candidats, dictionnaire, texte)
    assert (score.reference, score.trouvees, score.bonne_categorie) == (2, 2, 1)
    assert (score.candidats, score.justes) == (3, 2)
    assert score.rappel == 1.0
    assert score.precision == 2 / 3


def test_trouve_par_une_variante(dictionnaire):
    score = comparer([Candidat("CLIENT", ["NVL"])], dictionnaire, "Signé par Novaltis SA (NVL).")
    assert (score.reference, score.trouvees, score.bonne_categorie) == (1, 1, 1)


def test_rien_propose(dictionnaire):
    score = comparer([], dictionnaire, "Novaltis signe.")
    assert score.rappel == 0.0
    assert score.precision == 1.0
