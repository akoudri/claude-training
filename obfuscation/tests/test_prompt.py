import json

from obfuscation.detection.prompt import message_systeme, schema


def test_schema_limite_les_categories():
    s = schema(["CLIENT", "PERSONNE"])
    element = s["properties"]["entites"]["items"]
    assert element["properties"]["categorie"]["enum"] == ["CLIENT", "PERSONNE"]
    assert element["required"] == ["terme", "categorie"]
    assert s["required"] == ["entites"]


def test_message_definit_les_categories_demandees_seulement():
    message = message_systeme(["CLIENT", "PERSONNE"])
    assert "- CLIENT : " in message
    assert "- PERSONNE : " in message
    assert "LIEU" not in message  # ni dans les définitions ni dans l'exemple


def test_categorie_inconnue_recoit_une_definition_generique():
    assert "- SITE : nom propre relevant de la catégorie SITE" in message_systeme(["SITE"])


def test_exemple_valide_et_etranger_au_corpus_heron():
    message = message_systeme(["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"])
    reponse = json.loads(message.split("Réponse : ", 1)[1])
    assert {e["categorie"] for e in reponse["entites"]} == {"CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"}
    for terme in ("Novaltis", "Acme", "Héron", "Jeanne Martin"):
        assert terme not in message
