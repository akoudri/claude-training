"""Client minimal de l'API Ollama (/api/tags, /api/chat), sans dépendance."""
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from ..erreurs import ErreurConfiguration
from .prompt import message_systeme, schema

DELAI_VERIFICATION = 10.0
# Sans proxy, quelles que soient les variables http_proxy de l'environnement : le texte des documents ne doit
# jamais passer par un intermédiaire, même pour joindre la boucle locale.
SANS_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ErreurOllama(ErreurConfiguration):
    """Serveur injoignable ou modèle absent : rien ne peut être analysé."""


class ReponseInvalide(Exception):
    """Un appel a échoué (délai dépassé, réponse non conforme, erreur du serveur) : le morceau peut être retenté."""


@dataclass(frozen=True)
class Proposition:
    terme: str
    categorie: str


class ClientOllama:
    def __init__(self, url: str, modele: str, delai: float = 300.0):
        self.url = url.rstrip("/")
        self.modele = modele
        self.delai = delai

    def verifier(self) -> None:
        """Serveur joignable et modèle téléchargé ; « granite4.2 » désigne « granite4.2:latest »."""
        try:
            modeles = self._requete("/api/tags", delai=DELAI_VERIFICATION).get("models", [])
            noms = {m.get("name") for m in modeles}
        except (ReponseInvalide, AttributeError, TypeError) as e:
            raise ErreurOllama(f"le serveur {self.url} ne répond pas comme Ollama ({e})") from e
        if self.modele not in noms and f"{self.modele}:latest" not in noms:
            raise ErreurOllama(f"modèle « {self.modele} » absent du serveur Ollama {self.url} : ollama pull {self.modele}")

    def entites(self, texte: str, categories: list[str]) -> list[Proposition]:
        reponse = self._requete("/api/chat", {
            "model": self.modele,
            "stream": False,
            # Sans cela, un modèle à raisonnement (granite4.2) rédige plusieurs minutes de réflexion avant le JSON.
            "think": False,
            "format": schema(categories),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": message_systeme(categories)},
                {"role": "user", "content": texte},
            ],
        })
        try:
            entites = json.loads(reponse["message"]["content"])["entites"]
            return [Proposition(str(e["terme"]), str(e["categorie"])) for e in entites]
        except (KeyError, TypeError, ValueError) as e:
            raise ReponseInvalide("réponse du modèle non conforme au schéma") from e

    def _requete(self, chemin: str, corps: dict | None = None, delai: float | None = None) -> dict:
        delai = delai or self.delai
        donnees = None if corps is None else json.dumps(corps).encode("utf-8")
        requete = urllib.request.Request(self.url + chemin, data=donnees, headers={"Content-Type": "application/json"})
        try:
            with SANS_PROXY.open(requete, timeout=delai) as reponse:
                return json.loads(reponse.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ErreurOllama(f"modèle « {self.modele} » introuvable sur {self.url} : ollama pull {self.modele}") from e
            raise ReponseInvalide(f"Ollama a répondu {e.code}") from e
        except TimeoutError as e:
            raise ReponseInvalide(f"pas de réponse d'Ollama en {delai:g} s") from e
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ReponseInvalide(f"pas de réponse d'Ollama en {delai:g} s") from e
            raise ErreurOllama(
                f"Ollama injoignable à {self.url} ({e.reason}) ; pour la stack locale, depuis local-llm/ : "
                "docker compose up -d ollama"
            ) from e
        except OSError as e:  # connexion coupée en cours de réponse (modèle arrêté, mémoire saturée…)
            raise ReponseInvalide(f"connexion à Ollama interrompue ({e})") from e
        except ValueError as e:  # JSON illisible
            raise ReponseInvalide("réponse d'Ollama illisible") from e
