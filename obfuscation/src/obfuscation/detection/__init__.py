"""Détection des termes sensibles par un LLM local : du texte des documents au dictionnaire candidat."""
from collections.abc import Callable
from dataclasses import dataclass, field

from ..dictionnaire import Dictionnaire
from .candidats import Candidat, Collecte
from .decoupage import decouper
from .ollama import ErreurOllama, ReponseInvalide

CATEGORIES_PAR_DEFAUT = ["CLIENT", "PRESTATAIRE", "PROJET", "PERSONNE", "LIEU"]
MODELE_PAR_DEFAUT = "granite4.2:8b"
URL_PAR_DEFAUT = "http://127.0.0.1:11434"


@dataclass
class Bilan:
    candidats: list[Candidat]
    rejetees: int  # propositions absentes du texte
    ignores: list[str] = field(default_factory=list)  # « fichier — morceau i/n » non analysés
    interruption: str | None = None  # serveur perdu en cours d'analyse : les morceaux restants sont ignorés


def analyser(
    documents: list[tuple[str, str]],
    client,
    categories: list[str],
    exclus: Dictionnaire,
    signaler: Callable[[str, str], None] = lambda niveau, message: None,
) -> Bilan:
    """documents : (nom affiché, texte). `client` offre entites(texte, categories) (ClientOllama ou substitut).

    Un morceau en échec est retenté une fois, puis ignoré. Si le serveur est perdu (ErreurOllama), les morceaux
    restants sont ignorés sans appel, et les candidats déjà obtenus sont gardés : des heures d'analyse ne sont pas
    perdues.
    """
    collecte = Collecte(categories, exclus)
    ignores = []
    interruption = None
    for nom, texte in documents:
        morceaux = decouper(texte)
        for i, morceau in enumerate(morceaux, 1):
            etiquette = f"{nom} — morceau {i}/{len(morceaux)}"
            if interruption is not None:
                ignores.append(etiquette)
                continue
            signaler("analyse", etiquette)
            for essai in (1, 2):
                try:
                    collecte.ajouter(client.entites(morceau, categories), morceau)
                    break
                except ErreurOllama as e:
                    interruption = str(e)
                    ignores.append(etiquette)
                    break
                except ReponseInvalide as e:
                    if essai == 2:
                        signaler("avertissement", f"{etiquette} non analysé : {e}")
                        ignores.append(etiquette)
    texte_complet = "\n".join(texte for _, texte in documents)
    return Bilan(collecte.candidats(texte_complet), collecte.rejetees, ignores, interruption)
