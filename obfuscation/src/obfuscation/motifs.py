"""Motifs intégrés : valeurs reconnaissables sans dictionnaire (e-mail, téléphone, IBAN…)."""
import re
from collections.abc import Callable
from dataclasses import dataclass


def _toujours(_texte: str) -> bool:
    return True


@dataclass(frozen=True)
class Motif:
    categorie: str
    regex: re.Pattern
    valide: Callable[[str], bool] = _toujours


def luhn(chiffres: str) -> bool:
    """Clé de contrôle des SIREN et SIRET."""
    total = 0
    for rang, chiffre in enumerate(reversed(chiffres)):
        n = int(chiffre)
        if rang % 2:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _luhn_sans_espaces(texte: str) -> bool:
    return luhn(texte.replace(" ", ""))


def iban_valide(texte: str) -> bool:
    """Clé modulo 97 : les quatre premiers caractères passent à la fin, les lettres deviennent 10 à 35."""
    compact = texte.replace(" ", "").upper()
    reordonne = compact[4:] + compact[:4]
    return int("".join(str(int(c, 36)) for c in reordonne)) % 97 == 1


OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"

MOTIFS_INTEGRES: tuple[Motif, ...] = (
    Motif("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    # La ponctuation finale (point de fin de phrase, parenthèse fermante) ne fait pas partie de l'URL.
    Motif("URL", re.compile(r"https?://[^\s<>\"'\])]*[^\s<>\"'\]).,;:!?]", re.IGNORECASE)),
    Motif(
        "IBAN",
        re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?(?![A-Z0-9])"),
        iban_valide,
    ),
    Motif("SIRET", re.compile(r"(?<!\d)(?<!\d )\d{3} ?\d{3} ?\d{3} ?\d{5}(?! ?\d)"), _luhn_sans_espaces),
    Motif("SIREN", re.compile(r"(?<!\d)(?<!\d )\d{3} ?\d{3} ?\d{3}(?! ?\d)"), _luhn_sans_espaces),
    Motif(
        "TELEPHONE",
        re.compile(
            r"(?<![\w+])(?:(?:\+33 ?(?:\(0\) ?)?|0)[1-9](?:[ .-]?\d{2}){4}"
            r"|\+(?!33)[1-9]\d{0,2}(?:[ .-]?\d){6,12})(?!\d)"
        ),
    ),
    Motif("IP", re.compile(rf"(?<![\d.])(?:{OCTET}\.){{3}}{OCTET}(?!\d|\.\d)")),
)
