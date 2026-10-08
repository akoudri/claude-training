def test_obfusque_termes_et_motifs(moteur):
    texte = "Novaltis SA (NVL) pilote le Projet Héron ; contact : jeanne.martin@novaltis.example, contrat CTR-123456."
    assert moteur.transformer(texte, "obfusquer") == (
        "[CLIENT_1] ([CLIENT_1]) pilote le [PROJET_1] ; contact : [EMAIL_1], contrat [CONTRAT_1]."
    )


def test_le_plus_long_gagne_meme_contre_le_dictionnaire(moteur):
    # « novaltis » est dans le dictionnaire, mais l'adresse est plus longue : rien ne doit fuiter d'elle.
    assert moteur.transformer("j.martin@novaltis.example", "obfusquer") == "[EMAIL_1]"


def test_mots_entiers_seulement(moteur):
    assert moteur.transformer("Les Hérons de NVLX", "obfusquer") == "Les Hérons de NVLX"


def test_terme_finissant_par_un_point(moteur):
    assert moteur.transformer("Novaltis S.A. signe.", "obfusquer") == "[CLIENT_1] signe."


def test_table_partagee_entre_textes(moteur):
    moteur.transformer("Novaltis", "obfusquer")
    assert moteur.transformer("Héron et NVL", "obfusquer") == "[PROJET_1] et [CLIENT_1]"


def test_aller_retour_exact(moteur):
    texte = "Le Projet Héron de Novaltis : Jeanne Martin, 06 12 34 56 78."
    obfusque = moteur.transformer(texte, "obfusquer")
    assert "Novaltis" not in obfusque and "06 12" not in obfusque
    assert moteur.transformer(obfusque, "restaurer") == texte


def test_restauration_tolerante(moteur):
    moteur.transformer("Novaltis", "obfusquer")
    texte = "[CLIENT_1], **[CLIENT_1]**, \\[CLIENT_1\\], CLIENT_1, xCLIENT_1 et CLIENT_12"
    assert moteur.transformer(texte, "restaurer") == "Novaltis, **Novaltis**, Novaltis, Novaltis, xCLIENT_1 et CLIENT_12"
    assert moteur.inconnus == set()


def test_jetons_inconnus_signales(moteur):
    assert moteur.transformer("[CLIENT_9]", "restaurer") == "[CLIENT_9]"
    assert moteur.inconnus == {"[CLIENT_9]"}
