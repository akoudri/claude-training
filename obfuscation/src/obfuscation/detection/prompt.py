"""Message système et schéma de réponse demandés au modèle local."""
import json

DEFINITIONS = {
    "CLIENT": "organisation cliente, pour qui le travail est réalisé",
    "PRESTATAIRE": "entreprise qui réalise la prestation, ou sous-traitant",
    "PROJET": "nom propre d'un projet, d'un programme ou d'un produit",
    "PERSONNE": "nom d'une personne (prénom et nom, ou nom seul)",
    "LIEU": "ville, site, adresse ou bâtiment nommé",
}
# Exemple inventé, volontairement étranger au corpus Héron : la mesure ne doit pas être faussée.
EXEMPLE_TEXTE = (
    "Le Groupe Valmont a confié à Bellerive Conseil le programme Atlas. "
    "Marc Dubreuil, chef de projet, se rendra à Lorient. Le client valide chaque livrable."
)
EXEMPLE_ENTITES = [
    ("Groupe Valmont", "CLIENT"),
    ("Bellerive Conseil", "PRESTATAIRE"),
    ("Atlas", "PROJET"),
    ("Marc Dubreuil", "PERSONNE"),
    ("Lorient", "LIEU"),
]


def schema(categories: list[str]) -> dict:
    """Schéma JSON imposé à la réponse (champ « format » d'Ollama) : l'enum interdit toute catégorie inventée."""
    entite = {
        "type": "object",
        "properties": {"terme": {"type": "string"}, "categorie": {"type": "string", "enum": list(categories)}},
        "required": ["terme", "categorie"],
    }
    return {"type": "object", "properties": {"entites": {"type": "array", "items": entite}}, "required": ["entites"]}


def message_systeme(categories: list[str]) -> str:
    definitions = [f"- {c} : {DEFINITIONS.get(c, f'nom propre relevant de la catégorie {c}')}" for c in categories]
    exemple = {"entites": [{"terme": t, "categorie": c} for t, c in EXEMPLE_ENTITES if c in categories]}
    return "\n".join([
        "Tu repères les entités nommées sensibles d'un document professionnel, pour les masquer avant tout partage.",
        "Catégories :",
        *definitions,
        "",
        "Règles :",
        "- Recopie chaque terme exactement comme il est écrit dans le texte, sans le corriger ni le traduire.",
        "- Uniquement des noms propres : jamais de nom commun ni d'expression générique "
        "(« le client », « la société », « le projet »).",
        "- Une entrée par forme rencontrée : si un nom apparaît sous deux formes, donne les deux.",
        "- N'invente rien : si le texte ne contient aucune entité, renvoie une liste vide.",
        "",
        f"Exemple. Texte : « {EXEMPLE_TEXTE} »",
        f"Réponse : {json.dumps(exemple, ensure_ascii=False)}",
    ])
