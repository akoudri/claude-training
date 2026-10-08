import pytest

from obfuscation.detection import analyser
from obfuscation.detection.ollama import ErreurOllama, ReponseInvalide
from obfuscation.detection.ollama import Proposition as P
from obfuscation.dictionnaire import Dictionnaire

CATEGORIES = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]


class FauxClient:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def entites(self, texte, categories):
        self.appels.append(texte)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


def test_retient_les_termes_presents():
    client = FauxClient([[P("Novaltis", "PRESTATAIRE"), P("Inventé", "CLIENT")]])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire())
    assert [c.variantes for c in bilan.candidats] == [["Novaltis"]]
    assert bilan.rejetees == 1
    assert bilan.ignores == []


def test_retente_une_fois():
    client = FauxClient([ReponseInvalide("délai"), [P("Novaltis", "PRESTATAIRE")]])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire())
    assert len(client.appels) == 2
    assert len(bilan.candidats) == 1
    assert bilan.ignores == []


def test_ignore_un_morceau_apres_deux_echecs():
    messages = []
    client = FauxClient([ReponseInvalide("délai"), ReponseInvalide("délai")])
    bilan = analyser([("a.md", "Novaltis signe.")], client, CATEGORIES, Dictionnaire(), lambda n, m: messages.append((n, m)))
    assert bilan.ignores == ["a.md — morceau 1/1"]
    assert ("analyse", "a.md — morceau 1/1") in messages
    assert ("avertissement", "a.md — morceau 1/1 non analysé : délai") in messages


def test_document_sans_texte_aucun_appel():
    client = FauxClient([])
    bilan = analyser([("images.pptx", ""), ("vide.md", "  \n")], client, CATEGORIES, Dictionnaire())
    assert client.appels == []
    assert bilan.candidats == []


def test_ollama_injoignable_interrompt():
    client = FauxClient([ErreurOllama("injoignable")])
    with pytest.raises(ErreurOllama):
        analyser([("a.md", "texte")], client, CATEGORIES, Dictionnaire())
