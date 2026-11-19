import pytest
from faux_ollama import reponse_chat

from obfuscation.detection.ollama import ClientOllama, ErreurOllama, Proposition, ReponseInvalide

CATEGORIES = ["CLIENT", "PERSONNE"]


def test_envoie_modele_schema_et_temperature_nulle(faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([{"terme": "Novaltis", "categorie": "CLIENT"}]), 0)]
    propositions = ClientOllama(faux_ollama.url, "granite4.2:8b").entites("Signé avec Novaltis.", CATEGORIES)
    assert propositions == [Proposition("Novaltis", "CLIENT")]
    requete = faux_ollama.requetes[0]
    assert requete["model"] == "granite4.2:8b"
    assert requete["stream"] is False
    assert requete["think"] is False  # granite4.2 raisonnerait plusieurs minutes avant de répondre
    assert requete["options"]["temperature"] == 0
    assert requete["format"]["properties"]["entites"]["items"]["properties"]["categorie"]["enum"] == CATEGORIES
    assert requete["messages"][0]["role"] == "system"
    assert requete["messages"][1] == {"role": "user", "content": "Signé avec Novaltis."}


def test_verifier_accepte_le_modele(faux_ollama):
    ClientOllama(faux_ollama.url, "granite4.2:8b").verifier()


def test_verifier_accepte_un_nom_sans_etiquette(faux_ollama):
    faux_ollama.modeles = ["granite4.2:latest"]
    ClientOllama(faux_ollama.url, "granite4.2").verifier()


def test_verifier_signale_un_modele_absent(faux_ollama):
    with pytest.raises(ErreurOllama, match="ollama pull autre:1b"):
        ClientOllama(faux_ollama.url, "autre:1b").verifier()


def test_serveur_injoignable():
    with pytest.raises(ErreurOllama, match="docker compose up -d ollama"):
        ClientOllama("http://127.0.0.1:1", "granite4.2:8b").verifier()


def test_modele_introuvable_pendant_l_analyse(faux_ollama):
    faux_ollama.reponses = [(404, {"error": "model 'x' not found"}, 0)]
    with pytest.raises(ErreurOllama, match="ollama pull"):
        ClientOllama(faux_ollama.url, "x").entites("texte", CATEGORIES)


@pytest.mark.parametrize("corps", [
    {"message": {"content": "pas du json"}},
    {"message": {"content": '{"autre": []}'}},
    {"message": {"content": '{"entites": [{"terme": "X"}]}'}},
    {"inattendu": True},
    b"<html>pas du json</html>",
])
def test_reponse_non_conforme(faux_ollama, corps):
    faux_ollama.reponses = [(200, corps, 0)]
    with pytest.raises(ReponseInvalide):
        ClientOllama(faux_ollama.url, "granite4.2:8b").entites("texte", CATEGORIES)


def test_erreur_serveur(faux_ollama):
    faux_ollama.reponses = [(500, {"error": "out of memory"}, 0)]
    with pytest.raises(ReponseInvalide, match="500"):
        ClientOllama(faux_ollama.url, "granite4.2:8b").entites("texte", CATEGORIES)


def test_delai_depasse(faux_ollama):
    faux_ollama.reponses = [(200, reponse_chat([]), 1.0)]
    with pytest.raises(ReponseInvalide, match="pas de réponse"):
        ClientOllama(faux_ollama.url, "granite4.2:8b", delai=0.2).entites("texte", CATEGORIES)


def test_ignore_les_proxys_de_l_environnement(faux_ollama, monkeypatch):
    # Le texte des documents ne doit jamais partir vers un proxy, même configuré pour toutes les adresses.
    import urllib.request
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setattr(urllib.request, "_opener", None)
    ClientOllama(faux_ollama.url, "granite4.2:8b").verifier()
