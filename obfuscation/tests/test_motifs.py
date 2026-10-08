import pytest

from obfuscation.motifs import MOTIFS_INTEGRES, iban_valide, luhn


def trouver(categorie, texte):
    motif = next(m for m in MOTIFS_INTEGRES if m.categorie == categorie)
    return [m.group() for m in motif.regex.finditer(texte) if motif.valide(m.group())]


@pytest.mark.parametrize(
    "categorie, texte, attendu",
    [
        ("EMAIL", "Écrire à jeanne.martin@novaltis.example.", ["jeanne.martin@novaltis.example"]),
        ("EMAIL", "pas une adresse : novaltis@", []),
        (
            "URL",
            "Voir https://intranet.novaltis.fr/offres?id=3. Et (https://a.b/c)",
            ["https://intranet.novaltis.fr/offres?id=3", "https://a.b/c"],
        ),
        (
            "IBAN",
            "IBAN FR76 3000 6000 0112 3456 7890 189 ou FR7630006000011234567890189.",
            ["FR76 3000 6000 0112 3456 7890 189", "FR7630006000011234567890189"],
        ),
        ("IBAN", "clé fausse FR76 3000 6000 0112 3456 7890 188", []),
        ("SIRET", "SIRET 123 456 782 00010 et 12345678200010", ["123 456 782 00010", "12345678200010"]),
        ("SIRET", "commande 12345678901234", []),
        ("SIREN", "SIREN 123 456 782, mais pas dans 123 456 782 00010", ["123 456 782"]),
        ("SIREN", "référence 123456789", []),
        (
            "TELEPHONE",
            "01 23 45 67 89, 06.12.34.56.78, +33 6 12 34 56 78, +33 (0)1 23 45 67 89, +44 20 7946 0958",
            ["01 23 45 67 89", "06.12.34.56.78", "+33 6 12 34 56 78", "+33 (0)1 23 45 67 89", "+44 20 7946 0958"],
        ),
        ("TELEPHONE", "montant 1234567, année 2026", []),
        ("IP", "serveur 10.0.12.5, version 1.2.3.4.5, 256.1.1.1, fin 192.168.1.1.", ["10.0.12.5", "192.168.1.1"]),
    ],
)
def test_motifs(categorie, texte, attendu):
    assert trouver(categorie, texte) == attendu


def test_cles_de_controle():
    assert luhn("123456782") and not luhn("123456789")
    assert iban_valide("FR76 3000 6000 0112 3456 7890 189")
    assert not iban_valide("FR76 3000 6000 0112 3456 7890 188")
