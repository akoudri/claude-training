"""Applique à Open WebUI les réglages des tutoriels 01 et 02 qui ne passent pas par les variables d'environnement.

Lancé par le service ponctuel open-webui-init (docker-compose.yml), une fois Open WebUI démarré et les modèles
téléchargés. Il se connecte avec le compte administrateur de .env (WEBUI_ADMIN_EMAIL, WEBUI_ADMIN_PASSWORD) et :

- aligne le moteur d'extraction des documents sur docker-compose.docling.yml (tutoriel 01, section 6.2.1) : Docling
  si l'overlay est chargé ; retour à l'extracteur intégré s'il a été retiré ; un autre moteur choisi à la main est
  laissé tel quel ;
- règle le modèle de base (tutoriel 01, section 3) : think, max_tokens, temperature, function calling, capabilities ;
- si OPENWEBUI_EXEMPLES=true, crée la base « MBSE Expert » avec le corpus fictif (tutoriel 01, section 6.1) et
  l'assistant « Expert MBSE » (tutoriel 02, section 5).

Relançable sans effet de bord : le moteur d'extraction n'est modifié que s'il diffère de la valeur voulue, le modèle
de base est remis aux valeurs ci-dessous, la base et l'assistant ne sont créés que s'ils n'existent pas.
Bibliothèque standard uniquement.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

URL = os.environ.get("OPENWEBUI_URL", "http://open-webui:8080")
EXEMPLES = Path("/exemples")
FICHIERS_EXEMPLES = ["sow-exemple.md", "Proposition – Projet Héron, v2.md"]
DELAI_INDEXATION = 600  # secondes, par fichier

NOM_BASE = "MBSE Expert"
DESCRIPTION_BASE = (
    "Cahier des charges et proposition technique du Projet Héron : "
    "migration SysML v1 vers SysML v2 chez Acme Défense"
)
ID_ASSISTANT = "expert-mbse"
PROMPT_ASSISTANT = (
    "You are an MBSE expert. Answer only from the provided context. When the context\n"
    "lists items (deliverables, risks, work packages), list all of them. If the\n"
    "information is missing, say so explicitly. Cite sources as [n] and never mention\n"
    "source tags."
)

# Tutoriel 01, sections 3.1 et 3.2.
PARAMS_BASE = {"think": False, "max_tokens": 2048, "temperature": 0.3, "function_calling": "native"}
CAPABILITIES_BASE = {
    "file_upload": True, "file_context": True, "citations": True, "status_updates": True,
    "vision": False, "web_search": False, "image_generation": False, "code_interpreter": False,
    "terminal": False, "usage": False, "memory": True, "builtin_tools": False,
}
# Tutoriel 02, sections 5.2 à 5.4 : Legacy, sinon l'assistant ne lit pas sa base ; Memory décochée.
PARAMS_ASSISTANT = {**PARAMS_BASE, "function_calling": "legacy", "system": PROMPT_ASSISTANT}
CAPABILITIES_ASSISTANT = {**CAPABILITIES_BASE, "memory": False}

# Sans proxy : tout se passe sur le réseau Docker de la stack.
OUVREUR = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class Echec(Exception):
    pass


def appel(methode, chemin, jeton=None, corps=None, donnees=None, type_contenu=None, delai=60):
    entetes = {}
    if jeton:
        entetes["Authorization"] = f"Bearer {jeton}"
    if corps is not None:
        donnees = json.dumps(corps).encode()
        type_contenu = "application/json"
    if type_contenu:
        entetes["Content-Type"] = type_contenu
    requete = urllib.request.Request(URL + chemin, data=donnees, headers=entetes, method=methode)
    try:
        with OUVREUR.open(requete, timeout=delai) as reponse:
            contenu = reponse.read()
    except urllib.error.HTTPError as e:
        raise Echec(f"{methode} {chemin} : HTTP {e.code} {e.read().decode(errors='replace')[:300]}") from None
    return json.loads(contenu) if contenu else None


def connexion(email, mot_de_passe):
    for _ in range(60):  # Open WebUI répond avant d'avoir fini de créer le compte administrateur
        try:
            return appel("POST", "/api/v1/auths/signin", corps={"email": email, "password": mot_de_passe})["token"]
        except (Echec, urllib.error.URLError, ConnectionError):
            time.sleep(5)
    raise Echec("connexion impossible avec WEBUI_ADMIN_EMAIL / WEBUI_ADMIN_PASSWORD (compte créé avec "
                "d'autres valeurs, ou Open WebUI injoignable)")


def modele(jeton, identifiant):
    try:
        return appel("GET", f"/api/v1/models/model?id={urllib.request.quote(identifiant)}", jeton)
    except Echec:
        return None


def enregistrer_modele(jeton, formulaire):
    action = "update" if modele(jeton, formulaire["id"]) else "create"
    appel("POST", f"/api/v1/models/{'model/update' if action == 'update' else 'create'}", jeton, formulaire)
    return action


def regler_modele_de_base(jeton, nom):
    action = enregistrer_modele(jeton, {
        "id": nom, "base_model_id": None, "name": nom, "params": PARAMS_BASE,
        "meta": {"profile_image_url": "/static/favicon.png", "description": None,
                 "capabilities": CAPABILITIES_BASE, "knowledge": None, "tags": []},
    })
    print(f"modèle de base {nom} : réglé ({action})")


def docling_depuis_env(env):
    """Réglages Docling transmis par docker-compose.docling.yml, ou None si l'overlay n'est pas chargé."""
    if env.get("OPENWEBUI_DOCLING", "").lower() != "true":
        return None
    url = env.get("DOCLING_SERVER_URL", "")
    if not url:
        raise Echec("OPENWEBUI_DOCLING=true mais DOCLING_SERVER_URL est vide")
    try:
        params = json.loads(env.get("DOCLING_PARAMS") or "{}")
    except json.JSONDecodeError as e:
        raise Echec(f"DOCLING_PARAMS n'est pas du JSON valide : {e}") from None
    if not isinstance(params, dict):
        raise Echec("DOCLING_PARAMS doit être un objet JSON, par exemple {\"do_ocr\": \"false\"}")
    return {"url": url, "params": params}


def reglage_extraction(config, docling):
    """Champs à envoyer à /api/v1/retrieval/config/update (None si rien à changer) et libellé d'état.

    Overlay chargé : Docling, avec l'URL et les paramètres de l'overlay. Overlay retiré : retour à l'extracteur
    intégré, seulement si le moteur est encore Docling (un autre moteur, choisi à la main, est respecté).
    """
    moteur = config.get("CONTENT_EXTRACTION_ENGINE") or ""
    if docling:
        voulu = {"CONTENT_EXTRACTION_ENGINE": "docling", "DOCLING_SERVER_URL": docling["url"],
                 "DOCLING_PARAMS": docling["params"]}
        if all(config.get(cle) == valeur for cle, valeur in voulu.items()):
            return None, "Docling (inchangé)"
        return voulu, "Docling (réglé)"
    if moteur == "docling":
        return {"CONTENT_EXTRACTION_ENGINE": ""}, "extracteur intégré (Docling retiré)"
    return None, f"{moteur or 'extracteur intégré'} (inchangé)"


def synchroniser_extraction(jeton, docling):
    config = appel("GET", "/api/v1/retrieval/config", jeton)
    champs, etat = reglage_extraction(config, docling)
    if champs:
        appel("POST", "/api/v1/retrieval/config/update", jeton, champs)
    print(f"extraction des documents : {etat}")


def televerser(jeton, chemin):
    frontiere = uuid.uuid4().hex
    corps = (
        f"--{frontiere}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{chemin.name}"\r\n'
        "Content-Type: text/markdown\r\n\r\n"
    ).encode() + chemin.read_bytes() + f"\r\n--{frontiere}--\r\n".encode()
    fichier = appel("POST", "/api/v1/files/", jeton, donnees=corps,
                    type_contenu=f"multipart/form-data; boundary={frontiere}")
    limite = time.monotonic() + DELAI_INDEXATION
    while time.monotonic() < limite:
        etat = appel("GET", f"/api/v1/files/{fichier['id']}/process/status", jeton)
        if etat.get("status") == "completed":
            return fichier["id"]
        if etat.get("status") == "failed":
            raise Echec(f"indexation de {chemin.name} en échec : {etat}")
        time.sleep(2)
    raise Echec(f"indexation de {chemin.name} : délai de {DELAI_INDEXATION} s dépassé")


def base_existante(jeton):
    page = 1
    while True:
        reponse = appel("GET", f"/api/v1/knowledge/?page={page}", jeton)
        for base in reponse["items"]:
            if base["name"] == NOM_BASE:
                return base
        if not reponse["items"] or page * len(reponse["items"]) >= reponse["total"]:
            return None
        page += 1


def creer_base(jeton):
    base = base_existante(jeton)
    if base:
        print(f"base {NOM_BASE} : déjà présente, inchangée")
        return base
    base = appel("POST", "/api/v1/knowledge/create", jeton, {"name": NOM_BASE, "description": DESCRIPTION_BASE})
    for nom in FICHIERS_EXEMPLES:
        identifiant = televerser(jeton, EXEMPLES / nom)
        appel("POST", f"/api/v1/knowledge/{base['id']}/file/add", jeton, {"file_id": identifiant}, delai=DELAI_INDEXATION)
        print(f"base {NOM_BASE} : {nom} indexé")
    return base


def creer_assistant(jeton, modele_de_base, base):
    if modele(jeton, ID_ASSISTANT):
        print(f"assistant {ID_ASSISTANT} : déjà présent, inchangé")
        return
    enregistrer_modele(jeton, {
        "id": ID_ASSISTANT, "base_model_id": modele_de_base, "name": "Expert MBSE", "params": PARAMS_ASSISTANT,
        "meta": {"profile_image_url": "/static/favicon.png",
                 "description": "Assistant MBSE appuyé sur les documents Acme Défense",
                 "capabilities": CAPABILITIES_ASSISTANT, "tags": [],
                 "knowledge": [{"id": base["id"], "name": base["name"], "description": base["description"],
                                "type": "collection"}]},
    })
    print(f"assistant {ID_ASSISTANT} : créé, rattaché à la base {NOM_BASE}")


def main():
    email = os.environ.get("WEBUI_ADMIN_EMAIL", "")
    mot_de_passe = os.environ.get("WEBUI_ADMIN_PASSWORD", "")
    modele_de_base = os.environ["LLM_MODEL"]
    if not email or not mot_de_passe:
        print("WEBUI_ADMIN_EMAIL ou WEBUI_ADMIN_PASSWORD absent de .env : rien n'est configuré "
              "(réglages à faire à la main, tutoriels 01 et 02, y compris le moteur d'extraction si "
              "docker-compose.docling.yml est ajouté ou retiré : tutoriel 01, section 6.2.1)")
        return 0
    try:
        docling = docling_depuis_env(os.environ)
        jeton = connexion(email, mot_de_passe)
        synchroniser_extraction(jeton, docling)
        regler_modele_de_base(jeton, modele_de_base)
        if os.environ.get("OPENWEBUI_EXEMPLES", "").lower() == "true":
            creer_assistant(jeton, modele_de_base, creer_base(jeton))
        else:
            print("OPENWEBUI_EXEMPLES différent de true : base et assistant d'exemple non créés")
    except Echec as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
