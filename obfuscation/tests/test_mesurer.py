"""Le script de mesure ne doit afficher ni terme ni nom de fichier, même en cas d'erreur."""
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "exemples" / "mesurer.py"


@pytest.fixture
def mesurer():
    spec = importlib.util.spec_from_file_location("mesurer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_invalide_sans_fuite(mesurer, tmp_path, monkeypatch, capsys):
    reference = tmp_path / "Secret-Client.yaml"
    reference.write_text("CLIENT:\n  - Terme Secret\nPROJET:\n  - Terme Secret\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["mesurer.py", str(tmp_path), "--reference", str(reference)])
    assert mesurer.main() == 2
    sortie = capsys.readouterr()
    assert "Secret" not in sortie.out + sortie.err


def test_document_illisible_sans_fuite(mesurer, tmp_path, monkeypatch, capsys):
    (tmp_path / "Contrat Secret.md").write_text("texte", encoding="utf-8")

    def echec(fichier):
        raise ValueError(f"analyse impossible de {fichier}")

    monkeypatch.setattr(mesurer, "extraire", echec)
    assert mesurer.documents(tmp_path) == []
    sortie = capsys.readouterr()
    assert "Secret" not in sortie.out + sortie.err
    assert "document 1 illisible" in sortie.err
