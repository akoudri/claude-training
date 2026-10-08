from obfuscation.moteur import Remplacement
from obfuscation.segments import reecrire


def r(debut, fin, texte):
    return Remplacement(debut, fin, texte, "X_1")


def test_terme_coupe_sur_deux_segments():
    assert reecrire(["Nova", "ltis signe."], [r(0, 8, "[CLIENT_1]")]) == ["[CLIENT_1]", " signe."]


def test_terme_sur_plusieurs_segments_avec_segment_vide():
    textes = ["Le Pro", "", "jet Hé", "ron."]
    assert reecrire(textes, [r(3, 15, "[PROJET_1]")]) == ["Le [PROJET_1]", "", "", "."]


def test_plusieurs_remplacements():
    assert reecrire(["Novaltis et ", "Héron"], [r(0, 8, "[C_1]"), r(12, 17, "[P_1]")]) == ["[C_1] et ", "[P_1]"]


def test_sans_remplacement():
    assert reecrire(["a", "b"], []) == ["a", "b"]
