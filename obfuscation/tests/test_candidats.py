from obfuscation.detection.candidats import Collecte
from obfuscation.detection.ollama import Proposition as P
from obfuscation.dictionnaire import Dictionnaire, charger_dictionnaires

CATEGORIES = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]


def collecte(exclus=None, categories=CATEGORIES):
    return Collecte(list(categories), exclus or Dictionnaire())


def un_seul(c, texte):
    candidats = c.candidats(texte)
    assert len(candidats) == 1
    return candidats[0]


def test_terme_absent_du_texte_rejete():
    c = collecte()
    c.ajouter([P("Novaltys", "CLIENT")], "Signé avec Novaltis.")
    assert c.candidats("Signé avec Novaltis.") == []
    assert c.rejetees == 1


def test_terme_coupe_dans_un_mot_rejete():
    c = collecte()
    c.ajouter([P("Nova", "CLIENT")], "Signé avec Novaltis.")
    assert c.candidats("Signé avec Novaltis.") == []
    assert c.rejetees == 1


def test_forme_du_texte_conservee():
    c = collecte()
    texte = "Contrat L’Oréal Luxe signé."
    c.ajouter([P("l'oréal  luxe", "CLIENT")], texte)  # casse, apostrophe droite, espaces doublées
    assert un_seul(c, texte).variantes == ["L’Oréal Luxe"]


def test_filtrage_des_termes_courts_numeriques_et_generiques():
    c = collecte()
    texte = "Le Client SA, 2026."
    c.ajouter([P("SA", "CLIENT"), P("2026", "PROJET"), P("Client", "CLIENT")], texte)
    assert c.candidats(texte) == []
    assert c.ecartees == 3


def test_categorie_non_demandee_ecartee():
    c = collecte(categories=["CLIENT"])
    c.ajouter([P("Lyon", "LIEU")], "Réunion à Lyon.")
    assert c.candidats("Réunion à Lyon.") == []
    assert c.ecartees == 1


def test_termes_deja_connus_exclus(tmp_path):
    chemin = tmp_path / "client.yaml"
    chemin.write_text("CLIENT:\n  - Novaltis\n", encoding="utf-8")
    c = collecte(exclus=charger_dictionnaires([chemin]))
    c.ajouter([P("NOVALTIS", "PRESTATAIRE")], "Signé par NOVALTIS.")
    assert c.candidats("Signé par NOVALTIS.") == []
    assert c.ecartees == 1


def test_fusion_des_variantes_accentuees():
    c = collecte()
    premier, second = "Acme Défense signe. Acme Défense paie.", "Acme Defense valide."
    c.ajouter([P("Acme Défense", "CLIENT")], premier)
    c.ajouter([P("Acme Defense", "CLIENT")], second)
    candidat = un_seul(c, premier + "\n" + second)
    assert candidat.variantes == ["Acme Défense", "Acme Defense"]  # la plus fréquente d'abord
    assert candidat.occurrences == 3


def test_terme_inclus_devient_variante_presumee():
    c = collecte()
    texte = "Acme Défense signe. Acme paie."
    c.ajouter([P("Acme", "CLIENT"), P("Acme Défense", "CLIENT")], texte)
    candidat = un_seul(c, texte)
    assert candidat.variantes == ["Acme Défense"]
    assert candidat.presumees == ["Acme"]
    assert candidat.toutes == ["Acme Défense", "Acme"]
    assert candidat.occurrences == 2


def test_inclusion_par_mots_entiers_seulement():
    c = collecte()
    texte = "Acme et Acmeon Group."
    c.ajouter([P("Acme", "CLIENT"), P("Acmeon Group", "CLIENT")], texte)
    assert len(c.candidats(texte)) == 2


def test_inclusion_dans_la_meme_categorie_seulement():
    c = collecte()
    texte = "Le Projet Héron est mené par Héron Conseil."
    c.ajouter([P("Héron", "PROJET"), P("Héron Conseil", "PRESTATAIRE")], texte)
    assert len(c.candidats(texte)) == 2


def test_conflit_de_categorie_tranche_a_la_majorite():
    c = collecte()
    texte = "Novaltis réalise la prestation."
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "CLIENT")], texte)
    candidat = un_seul(c, texte)
    assert candidat.categorie == "PRESTATAIRE"
    assert candidat.autres_categories == ["CLIENT"]


def test_egalite_tranchee_par_l_ordre_des_categories():
    c = collecte()
    texte = "Novaltis réalise la prestation."
    c.ajouter([P("Novaltis", "PRESTATAIRE")], texte)
    c.ajouter([P("Novaltis", "CLIENT")], texte)
    assert un_seul(c, texte).categorie == "CLIENT"


def test_ordre_et_contexte():
    c = collecte()
    texte = "x" * 100 + " Jeanne Martin écrit à Paul Durand. Jeanne Martin relance. " + "y" * 100
    c.ajouter([P("Paul Durand", "PERSONNE"), P("Jeanne Martin", "PERSONNE")], texte)
    candidats = c.candidats(texte)
    assert [k.variantes[0] for k in candidats] == ["Jeanne Martin", "Paul Durand"]  # par occurrences décroissantes
    contexte = candidats[0].contexte
    assert contexte.startswith("…") and contexte.endswith("…")
    assert "Jeanne Martin" in contexte


def test_expression_sans_majuscule_ecartee():
    c = collecte()
    texte = "Le prestataire travaille dans les locaux du client, puis chez le Groupe Valmont."
    c.ajouter([P("le prestataire", "PRESTATAIRE"), P("locaux du client", "LIEU"), P("le Groupe Valmont", "CLIENT")], texte)
    assert [k.variantes for k in c.candidats(texte)] == [["le Groupe Valmont"]]
    assert c.ecartees == 2


def test_mots_generiques_precedes_d_un_article_ecartes():
    c = collecte()
    texte = "Ci-après le Client. Le Prestataire livre. Les Clients valident."
    c.ajouter([P("le Client", "CLIENT"), P("Le Prestataire", "PRESTATAIRE"), P("Les Clients", "CLIENT")], texte)
    assert c.candidats(texte) == []
    assert c.ecartees == 3
