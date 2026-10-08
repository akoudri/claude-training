"""Post-traitement déterministe des propositions du modèle : rien n'est proposé qui ne figure dans le texte."""
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..dictionnaire import APRES, AVANT, Dictionnaire, motif_de_terme, normaliser
from .ollama import Proposition

LONGUEUR_MIN = 3
CONTEXTE = 40  # caractères de part et d'autre de la première occurrence
MOTS_GENERIQUES = frozenset(normaliser(mot) for mot in (
    "client", "clients", "société", "entreprise", "prestataire", "fournisseur", "titulaire", "partenaire",
    "projet", "programme", "direction", "équipe", "service", "département", "groupe", "comité de pilotage",
))


@dataclass
class Candidat:
    categorie: str
    variantes: list[str]  # la première est celle que « restaurer » remettra en place
    occurrences: int = 0
    contexte: str = ""
    presumees: list[str] = field(default_factory=list)  # termes inclus dans une variante : à vérifier
    autres_categories: list[str] = field(default_factory=list)

    @property
    def toutes(self) -> list[str]:
        return [*self.variantes, *self.presumees]


def _recherche(termes: list[str]) -> re.Pattern:
    """Mêmes règles de correspondance que les dictionnaires ; les plus longs termes d'abord."""
    alternatives = "|".join(motif_de_terme(t) for t in sorted(termes, key=len, reverse=True))
    return re.compile(rf"{AVANT}(?:{alternatives}){APRES}", re.IGNORECASE)


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", normaliser(texte)) if not unicodedata.combining(c))


def _contient(long: str, court: str) -> bool:
    return long != court and re.search(rf"(?<!\w){re.escape(court)}(?!\w)", long) is not None


class Collecte:
    def __init__(self, categories: list[str], exclus: Dictionnaire):
        self.categories = categories
        self.exclus = exclus
        self.rejetees = 0  # propositions absentes du texte : inventées ou déformées par le modèle
        self.ecartees = 0  # filtrées, hors des catégories demandées, ou déjà dans un dictionnaire
        self._votes: dict[str, Counter] = defaultdict(Counter)  # clé normalisée → catégories proposées
        self._formes: dict[str, Counter] = defaultdict(Counter)  # clé normalisée → formes trouvées dans le texte

    def ajouter(self, propositions: list[Proposition], morceau: str) -> None:
        for proposition in propositions:
            terme = " ".join(proposition.terme.split())
            if (
                proposition.categorie not in self.categories
                or len(terme) < LONGUEUR_MIN
                or not any(c.isalpha() for c in terme)
                or normaliser(terme) in MOTS_GENERIQUES
            ):
                self.ecartees += 1
                continue
            trouve = _recherche([terme]).search(morceau)
            if trouve is None:
                self.rejetees += 1
                continue
            forme = " ".join(trouve.group().split())  # la forme du texte, pas celle du modèle
            if self.exclus.terme(forme) is not None:
                self.ecartees += 1
                continue
            cle = normaliser(forme)
            self._votes[cle][proposition.categorie] += 1
            self._formes[cle][forme] += 1

    def candidats(self, texte: str) -> list[Candidat]:
        """`texte` : l'ensemble des documents, pour compter les occurrences et citer un contexte."""
        rang = {c: i for i, c in enumerate(self.categories)}
        entrees = []
        for cle, votes in self._votes.items():
            classement = sorted(votes, key=lambda c: (-votes[c], rang[c]))
            forme = self._formes[cle].most_common(1)[0][0]
            entrees.append(Candidat(classement[0], [forme], autres_categories=classement[1:]))
        entrees = _fusionner_inclus(_fusionner_accents(entrees))
        for candidat in entrees:
            _compter(candidat, texte)
        return sorted(entrees, key=lambda c: (rang[c.categorie], -c.occurrences, c.variantes[0]))


def _ajouter_categories(cible: Candidat, source: Candidat) -> None:
    cible.autres_categories += [c for c in source.autres_categories if c not in cible.autres_categories]


def _fusionner_accents(entrees: list[Candidat]) -> list[Candidat]:
    """« Acme Défense » et « Acme Defense » : une entrée, deux variantes."""
    groupes: dict[tuple[str, str], Candidat] = {}
    for entree in entrees:
        cle = (entree.categorie, _sans_accents(entree.variantes[0]))
        if cle in groupes:
            groupes[cle].variantes += entree.variantes
            _ajouter_categories(groupes[cle], entree)
        else:
            groupes[cle] = entree
    return list(groupes.values())


def _fusionner_inclus(entrees: list[Candidat]) -> list[Candidat]:
    """« Acme », contenu par mots entiers dans « Acme Défense » (même catégorie), en devient une variante présumée.

    Du plus court au plus long : un terme rejoint le plus court de ceux qui le contiennent, et le suit si celui-ci
    est à son tour inclus dans un terme plus long.
    """
    restants = sorted(entrees, key=lambda e: len(e.variantes[0]))
    resultat = []
    for i, court in enumerate(restants):
        hote = next((
            long for long in restants[i + 1:]
            if long.categorie == court.categorie
            and any(_contient(_sans_accents(l), _sans_accents(c)) for l in long.variantes for c in court.variantes)
        ), None)
        if hote is None:
            resultat.append(court)
        else:
            hote.presumees += court.toutes
            _ajouter_categories(hote, court)
    return resultat


def _compter(candidat: Candidat, texte: str) -> None:
    comptes = {v: len(_recherche([v]).findall(texte)) for v in candidat.variantes}
    candidat.variantes.sort(key=lambda v: (-comptes[v], v))
    trouves = list(_recherche(candidat.toutes).finditer(texte))
    candidat.occurrences = len(trouves)
    if trouves:
        debut, fin = max(0, trouves[0].start() - CONTEXTE), trouves[0].end() + CONTEXTE
        extrait = " ".join(texte[debut:fin].split())
        candidat.contexte = ("…" if debut > 0 else "") + extrait + ("…" if fin < len(texte) else "")
