import pytest
from documents import DICO

from obfuscation.dictionnaire import charger_dictionnaires
from obfuscation.moteur import Moteur
from obfuscation.table import Table


@pytest.fixture
def dictionnaire(tmp_path):
    chemin = tmp_path / "dico.yaml"
    chemin.write_text(DICO, encoding="utf-8")
    return charger_dictionnaires([chemin])


@pytest.fixture
def moteur(dictionnaire):
    return Moteur(dictionnaire, Table())
