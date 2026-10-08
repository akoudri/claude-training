from obfuscation.detection.decoupage import decouper


def test_texte_court_un_seul_morceau():
    assert decouper("Un.\nDeux.") == ["Un.\nDeux."]


def test_lignes_vides_ignorees():
    assert decouper("\n\nUn.\n\n  \nDeux.\n") == ["Un.\nDeux."]
    assert decouper("  \n") == []


def test_coupe_aux_paragraphes_avec_chevauchement():
    paragraphes = [f"Paragraphe {i} " + "x" * 30 for i in range(10)]  # 43 caractères chacun
    morceaux = decouper("\n".join(paragraphes), taille=100)
    assert len(morceaux) == 9
    assert all(len(m) <= 100 for m in morceaux)
    for p in paragraphes:
        assert any(p in m.split("\n") for m in morceaux)
    for avant, apres in zip(morceaux, morceaux[1:]):
        assert apres.split("\n")[0] == avant.split("\n")[-1]  # le dernier paragraphe ouvre le morceau suivant


def test_paragraphe_trop_long_coupe_en_fin_de_phrase():
    texte = ("Le prestataire livre le rapport. " * 10).strip()
    morceaux = decouper(texte, taille=100)
    assert all(len(m) <= 100 for m in morceaux)
    assert all(m.endswith(".") for m in morceaux)
    assert " ".join(morceaux).split() == texte.split()


def test_sans_fin_de_phrase_coupe_sur_une_espace():
    texte = ("mot " * 50).strip()
    morceaux = decouper(texte, taille=100)
    assert all(len(m) <= 100 for m in morceaux)
    assert " ".join(morceaux).split() == texte.split()


def test_sans_espace_coupe_net():
    assert decouper("x" * 250, taille=100) == ["x" * 100, "x" * 100, "x" * 50]
