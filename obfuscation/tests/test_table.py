import json
import stat

import pytest

from obfuscation.erreurs import ErreurTable
from obfuscation.table import Table


def test_attribue_des_jetons_numerotes_par_categorie():
    table = Table()
    assert table.jeton_pour("CLIENT", "Novaltis") == "[CLIENT_1]"
    assert table.jeton_pour("CLIENT", "Acme") == "[CLIENT_2]"
    assert table.jeton_pour("PROJET", "Héron") == "[PROJET_1]"


def test_meme_valeur_meme_jeton_sans_tenir_compte_de_la_casse():
    table = Table()
    assert table.jeton_pour("EMAIL", "J.Martin@novaltis.fr") == table.jeton_pour("EMAIL", "j.martin@NOVALTIS.fr")
    assert table.valeur("EMAIL_1") == "J.Martin@novaltis.fr"
    assert table.valeur("EMAIL_2") is None


def test_sauvegarde_puis_rechargement_continue_la_numerotation(tmp_path):
    chemin = tmp_path / "client.table.json"
    table = Table()
    table.jeton_pour("CLIENT", "Novaltis")
    table.sauvegarder(chemin)
    assert json.loads(chemin.read_text(encoding="utf-8")) == {"version": 1, "jetons": {"[CLIENT_1]": "Novaltis"}}
    rechargee = Table.charger(chemin)
    assert rechargee.jeton_pour("CLIENT", "Novaltis") == "[CLIENT_1]"
    assert rechargee.jeton_pour("CLIENT", "Acme") == "[CLIENT_2]"


def test_table_absente_donne_une_table_vide(tmp_path):
    assert Table.charger(tmp_path / "absente.table.json").jetons == {}


def test_sauvegarde_atomique_lisible_par_le_seul_proprietaire(tmp_path):
    chemin = tmp_path / "t.table.json"
    Table().sauvegarder(chemin)
    assert stat.S_IMODE(chemin.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [chemin]


@pytest.mark.parametrize(
    "contenu",
    [
        "pas du json",
        '{"version": 2, "jetons": {}}',
        '{"version": 1, "jetons": {"CLIENT_1": "Novaltis"}}',
        '{"version": 1, "jetons": {"[CLIENT_1]": 3}}',
    ],
)
def test_table_invalide_refusee(tmp_path, contenu):
    chemin = tmp_path / "t.table.json"
    chemin.write_text(contenu, encoding="utf-8")
    with pytest.raises(ErreurTable):
        Table.charger(chemin)
