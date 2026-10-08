"""Table de correspondance entre jetons et valeurs réelles. Elle ne doit jamais quitter la machine."""
import json
import os
import re
import tempfile
from pathlib import Path

from .erreurs import ErreurTable

VERSION = 1
FORME_JETON = re.compile(r"\[([A-Z][A-Z0-9_]*)_(\d+)\]")


class Table:
    def __init__(self, jetons: dict[str, str] | None = None):
        self.jetons: dict[str, str] = {}
        self._index: dict[tuple[str, str], str] = {}
        self._compteurs: dict[str, int] = {}
        for jeton, valeur in (jetons or {}).items():
            forme = FORME_JETON.fullmatch(jeton)
            if forme is None or not isinstance(valeur, str):
                raise ErreurTable(f"entrée invalide dans la table : {jeton!r}")
            self._enregistrer(jeton, forme.group(1), int(forme.group(2)), valeur)

    def _enregistrer(self, jeton: str, categorie: str, numero: int, valeur: str) -> None:
        self.jetons[jeton] = valeur
        self._index[(categorie, valeur.casefold())] = jeton
        self._compteurs[categorie] = max(self._compteurs.get(categorie, 0), numero)

    def jeton_pour(self, categorie: str, valeur: str) -> str:
        """Jeton de la valeur, créé au besoin ; une même valeur (casse ignorée) garde toujours le même jeton."""
        cle = (categorie, valeur.casefold())
        if cle not in self._index:
            numero = self._compteurs.get(categorie, 0) + 1
            self._enregistrer(f"[{categorie}_{numero}]", categorie, numero, valeur)
        return self._index[cle]

    def valeur(self, jeton_nu: str) -> str | None:
        return self.jetons.get(f"[{jeton_nu}]")

    @classmethod
    def charger(cls, chemin: Path) -> "Table":
        if not chemin.exists():
            return cls()
        try:
            donnees = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ErreurTable(f"{chemin} : table illisible ({e})") from e
        if not isinstance(donnees, dict) or donnees.get("version") != VERSION or not isinstance(donnees.get("jetons"), dict):
            raise ErreurTable(f"{chemin} : format de table inconnu")
        try:
            return cls(donnees["jetons"])
        except ErreurTable as e:
            raise ErreurTable(f"{chemin} : {e}") from e

    def sauvegarder(self, chemin: Path) -> None:
        """Écriture atomique ; le fichier temporaire de mkstemp a les droits 0600, conservés par le renommage."""
        chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = json.dumps({"version": VERSION, "jetons": self.jetons}, ensure_ascii=False, indent=2) + "\n"
        descripteur, temporaire = tempfile.mkstemp(dir=chemin.parent, prefix=f".{chemin.name}.", suffix=".tmp")
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8") as fichier:
                fichier.write(contenu)
            os.replace(temporaire, chemin)
        except BaseException:
            Path(temporaire).unlink(missing_ok=True)
            raise
