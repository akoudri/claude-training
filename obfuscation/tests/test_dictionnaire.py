import textwrap

import pytest

from obfuscation.dictionnaire import Terme, charger_dictionnaires
from obfuscation.erreurs import ErreurDictionnaire


def ecrire(tmp_path, contenu, nom="dico.yaml"):
    chemin = tmp_path / nom
    chemin.write_text(textwrap.dedent(contenu), encoding="utf-8")
    return chemin


def test_variantes_associees_a_la_forme_canonique(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, """
        CLIENT:
          - [Novaltis, Novaltis SA, NVL]
          - Acme
        """)])
    assert dictionnaire.terme("nvl") == Terme("CLIENT", "Novaltis")
    assert dictionnaire.terme("NOVALTIS  sa") == Terme("CLIENT", "Novaltis")
    assert dictionnaire.terme("ACME") == Terme("CLIENT", "Acme")
    assert dictionnaire.terme("Inconnu") is None


def test_recherche_mots_entiers_casse_et_espaces_insecables(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, """
        PROJET:
          - [Projet Héron, Héron]
        """)])
    texte = "Le projet héron, les Hérons et HÉRON."
    trouves = [m.group(1) for m in dictionnaire.recherche.finditer(texte)]
    assert trouves == ["projet héron", "héron", "HÉRON"]


def test_plusieurs_dictionnaires_fusionnes(tmp_path):
    dictionnaire = charger_dictionnaires([
        ecrire(tmp_path, "CLIENT:\n  - Novaltis\n", "a.yaml"),
        ecrire(tmp_path, "PROJET:\n  - Héron\n", "b.yaml"),
    ])
    assert dictionnaire.terme("novaltis").categorie == "CLIENT"
    assert dictionnaire.terme("héron").categorie == "PROJET"


def test_meme_terme_dans_deux_categories_refuse_avec_positions(tmp_path):
    a = ecrire(tmp_path, "CLIENT:\n  - Héron\n", "a.yaml")
    b = ecrire(tmp_path, "PROJET:\n  - Projet X\n  - héron\n", "b.yaml")
    with pytest.raises(ErreurDictionnaire) as erreur:
        charger_dictionnaires([a, b])
    message = str(erreur.value)
    assert f"{b}:3" in message and "CLIENT" in message and f"{a}:2" in message


def test_motifs_personnalises(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, r"""
        motifs:
          CONTRAT: 'CTR-\d{6}'
        """)])
    assert dictionnaire.motifs["CONTRAT"].fullmatch("CTR-123456")
    assert dictionnaire.recherche is None


def test_dictionnaire_vide(tmp_path):
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, "")])
    assert dictionnaire.termes == {} and dictionnaire.recherche is None


@pytest.mark.parametrize(
    "contenu, attendu",
    [
        ("client:\n  - x\n", "dico.yaml:1"),
        ("CLIENT: Novaltis\n", "dico.yaml:1"),
        ("CLIENT:\n  - [Novaltis, '']\n", "dico.yaml:2"),
        ("motifs:\n  CONTRAT: 'CTR-(\\d'\n", "dico.yaml:2"),
        ("CLIENT: [\n", "YAML invalide"),
        ("- Novaltis\n", "dico.yaml:1"),
    ],
)
def test_erreurs_signalees_avec_position(tmp_path, contenu, attendu):
    with pytest.raises(ErreurDictionnaire, match=attendu.replace(".", r"\.")):
        charger_dictionnaires([ecrire(tmp_path, contenu)])


def test_variante_retrouvee_malgre_les_ecarts_de_casse_unicode(tmp_path):
    # « İ » (I turc) correspond à « i » pour re.IGNORECASE, mais « İ ».casefold() vaut « i̇ ».
    dictionnaire = charger_dictionnaires([ecrire(tmp_path, "CLIENT:\n  - Istanbul Conseil\n")])
    trouve = next(dictionnaire.recherche.finditer("chez İstanbul Conseil")).group(1)
    assert dictionnaire.terme(trouve) == Terme("CLIENT", "Istanbul Conseil")
