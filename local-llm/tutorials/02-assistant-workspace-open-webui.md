# Créer un assistant dans le Workspace d'Open WebUI

Ce guide explique comment assembler un **assistant spécialisé** (un « agent ») dans Open WebUI 0.11 : un modèle, des consignes, une base de documents et, si besoin, des outils. Il prend pour exemple l'assistant **Expert MBSE** construit sur `granite4.2:8b` et la base **MBSE Expert**.

Il fait suite à [Configurer Open WebUI pour un LLM local](01-configuration-open-webui.md), qui couvre les réglages de la plateforme (paramètres du modèle de base, tâches d'arrière-plan, RAG).

---

## 1. Ce qu'est le Workspace

Le **Workspace** (menu de gauche) est la section où l'on fabrique des éléments réutilisables dans toutes les conversations. On ne « crée pas un workspace » : il en existe un seul, et on y crée des éléments, onglet par onglet.

| Onglet | Ce qu'on y crée | Rôle dans un assistant |
|---|---|---|
| **Models** | Des **assistants** : un modèle existant + un prompt système + des paramètres + des bases et des outils attachés. | L'assistant lui-même, qui apparaît dans le sélecteur de modèle comme un modèle à part. |
| **Knowledge** | Des **bases de connaissances** : des documents indexés dans pgvector. | Ce que l'assistant sait. |
| **Tools** | Des **outils** en Python que le modèle peut appeler. | Ce que l'assistant sait faire. |
| **Prompts** | Des modèles de messages appelés par `/`. | Facultatif : raccourcis pour les questions fréquentes. |
| **Skills** | Des fiches d'instructions que le modèle charge à la demande. | Facultatif, peu utile avec un modèle de 8B. |

Les **Notes**, dans le menu de gauche, et la **Memory**, dans les réglages personnels, ne font pas partie du Workspace, mais elles complètent un assistant : voir la section 9.

Le bouton **Create**, en haut à droite, crée toujours un élément **de l'onglet affiché**.

### Workspace ou Admin Panel ?

| | Admin Panel → Settings → Models | Workspace → Models |
|---|---|---|
| Ce qu'on règle | Les **modèles de base** fournis par Ollama | Les **assistants** construits dessus |
| Nature des réglages | Techniques, valables pour tout usage : think, max_tokens, temperature | Métier, propres à un usage : prompt système, documents, outils |
| Qui | L'administrateur | Tout utilisateur autorisé |

> **Règle pratique** : ne mettez pas de prompt métier sur le modèle de base. Une consigne comme « réponds uniquement à partir du contexte » s'appliquerait à toutes les conversations, et le modèle refuserait de répondre aux questions générales. Gardez le modèle de base généraliste, et créez un assistant par usage.

---

## 2. Ordre de construction

Un assistant référence des bases et des outils : il faut donc **les créer avant lui**.

```text
1. Knowledge  →  2. Tools (facultatif)  →  3. Models (l'assistant)  →  4. Tests
```

---

## 3. Étape 1 : la base de connaissances

**Workspace → Knowledge → Create**

1. **Nom** : `MBSE Expert`.
2. **Description** : décrivez le **contenu** (« Rapports, cahiers des charges et cadres méthodologiques sur SysML v2 et le MBSE chez Acme Défense »). Elle aide les utilisateurs à choisir la bonne base, et le modèle à décider de la consulter en mode Native (voir 5.4).
3. **Ajouter les documents** par glisser-déposer, ou avec le bouton **+** de la base. Attendez la fin de l'indexation de chaque fichier.

| Bonne pratique | Pourquoi |
|---|---|
| Préférer **DOCX ou Markdown** au PDF | Le PDF aplatit les tableaux et transforme la table des matières et les pieds de page en extraits parasites. Une question sur un tableau extrait d'un PDF a attribué une information au mauvais acteur. |
| **Une seule version** de chaque document | Un même rapport en PDF et en DOCX produit des extraits en double, qui occupent les places du Top K. |
| Une base **par domaine** | Une base fourre-tout dilue la recherche. Mieux vaut plusieurs bases, attachées au bon assistant. |

**Remplacer un document** : survolez-le dans la liste de la base, supprimez-le (✕), puis ajoutez la nouvelle version. Vérifiez ensuite qu'aucun extrait de l'ancienne version ne reste (voir section 7).

---

## 4. Étape 2 : les outils (facultatif)

Un outil est une fonction que le modèle peut décider d'appeler : interroger une API, lancer un workflow n8n, faire un calcul exact, lire une date. Il en existe deux sortes.

### 4.1 Outil Python (Workspace → Tools)

**Workspace → Tools → Create**, puis collez le code. Open WebUI lit la classe `Tools` :

- chaque **méthode publique** devient un outil ;
- sa **docstring** et ses **annotations de type** forment la description envoyée au modèle. Elles doivent être claires, car c'est tout ce que le modèle sait de l'outil ;
- les **Valves** sont des réglages modifiables depuis l'interface (URL, clé d'API…), sans toucher au code.

Exemple : un outil qui transmet une question à un workflow n8n de la stack. Open WebUI et n8n sont sur le même réseau Docker, et n8n y est joignable sous le nom `n8n`.

```python
"""
title: Workflow n8n MBSE
description: Envoie une question à un workflow n8n et renvoie sa réponse.
version: 0.1.0
"""

import requests
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        webhook_url: str = Field(
            default="http://n8n:5678/webhook/mbse",
            description="URL du webhook n8n (nœud Webhook, méthode POST)",
        )
        timeout: int = Field(default=120, description="Délai maximal en secondes")

    def __init__(self):
        self.valves = self.Valves()

    def ask_mbse_workflow(self, question: str) -> str:
        """
        Forward a question to the MBSE n8n workflow and return its answer.
        Use it when the user asks to run the MBSE analysis workflow.
        :param question: The user's question, rephrased as a standalone request.
        :return: The workflow's answer as plain text.
        """
        response = requests.post(
            self.valves.webhook_url,
            json={"question": question},
            timeout=self.valves.timeout,
        )
        response.raise_for_status()
        return response.text
```

Après **Save**, ouvrez les **Valves** de l'outil (icône engrenage dans la liste) pour ajuster l'URL.

> Le code d'un outil s'exécute **dans le conteneur Open WebUI**, avec ses droits. N'installez que du code que vous avez lu.

### 4.2 Serveur d'outils externe (OpenAPI ou MCP)

Pour des outils qui existent déjà sous forme de service, il n'y a pas de code à écrire dans Open WebUI : on déclare le serveur.

**Admin Panel → Settings → Integrations** (section *Tool Servers*) → ajouter une connexion de type **OpenAPI** ou **MCP**, avec son URL.

- Le serveur doit être **joignable en HTTP depuis le conteneur Open WebUI**. Un serveur MCP en mode `stdio`, comme les exemples de ce dépôt, doit d'abord être exposé en HTTP, par exemple avec le proxy `mcpo` ou un transport *Streamable HTTP*.
- Une fois déclarés, les outils du serveur se sélectionnent dans un assistant comme les outils Python.

---

## 5. Étape 3 : l'assistant

**Workspace → Models → Create**

### 5.1 Identité et consignes

| Champ | Valeur (exemple) | Ce que ça implique |
|---|---|---|
| **Name** | `Expert MBSE` | Le nom affiché dans le sélecteur de modèle. |
| **Base Model** | `granite4.2:8b` | Le modèle qui génère les réponses. |
| **Description** | `Assistant MBSE appuyé sur les documents Acme Défense` | Visible dans le sélecteur, pour aider les utilisateurs à choisir. |
| **System Prompt** | voir ci-dessous | Les consignes de l'assistant, ajoutées à chaque conversation. |

```text
You are an MBSE expert. Answer only from the provided context. When the context
lists items (deliverables, risks, work packages), list all of them. If the
information is missing, say so explicitly. Cite sources as [n] and never mention
source tags.
```

Le rôle de chaque consigne est expliqué dans le [guide de configuration, §3.3](01-configuration-open-webui.md#33-system-prompt).

### 5.2 Advanced Params

Cliquez sur **Show** à côté d'*Advanced Params*. Les paramètres du modèle de base ne sont pas toujours hérités : **reportez explicitement** ceux qui comptent.

| Paramètre | Valeur | Pourquoi |
|---|---|---|
| **think (Ollama)** | Off | Sans ça, le modèle peut réfléchir plusieurs minutes sans rien afficher. |
| **max_tokens** | 2048 | Limite la longueur des réponses, et donc leur durée. |
| **temperature** | 0.3 | Réponses plus fidèles aux documents, moins d'invention. |
| **Function Calling** | **Legacy** pour un assistant documentaire (voir 5.4) | Détermine si la recherche documentaire est automatique ou laissée au modèle. |
| **top_k** | **Default** | ⚠️ Ce n'est **pas** le Top K du RAG. C'est un paramètre d'échantillonnage : à chaque mot, le modèle choisit parmi les *k* mots les plus probables. Le nombre d'extraits se règle dans *Admin Panel → Settings → Documents*. |

Le bouton *Function Calling* tourne en boucle à chaque clic : **Default → Native → Legacy → Default**.

### 5.3 Knowledge, Tools, Capabilities

- **Knowledge** : cliquez sur le lien gris **Select Knowledge**, puis choisissez la base, l'élément marqué *Collection* et pas un fichier isolé. Une étiquette « MBSE Expert » doit apparaître. La phrase *« To attach knowledge base here, add them to the "Knowledge" workspace first »* s'affiche simplement tant que rien n'est sélectionné. N'utilisez pas le lien **Upload** : il rattache un fichier seul, hors de la base.
- **Tools** : cochez les outils créés à l'étape 2. Ils seront proposés dans les conversations avec cet assistant.
- **Capabilities** :

| Capability | Assistant documentaire | Raison |
|---|---|---|
| File Upload, File Context, Citations, Status Updates | ✅ | Joindre un document, voir les extraits utilisés, suivre l'avancement. |
| Vision, Image Generation, Code Interpreter, Web Search, Terminal | ❌ | Non supportés par le modèle ou non configurés dans la stack. |
| Memory | ❌ conseillé | Sinon, des souvenirs d'autres conversations s'ajoutent au contexte, ce qui va contre « answer only from the provided context ». |
| Builtin Tools | ❌ en Legacy | Voir 5.4. |

Validez avec **Save & Create**, ou **Save & Update** pour une modification.

### 5.4 Le choix décisif : Legacy ou Native

C'est le réglage le moins visible et le plus important. Open WebUI ne traite pas une base rattachée à un assistant de la même façon selon le mode de *Function Calling* :

| | **Legacy** | **Native** (ou Default) |
|---|---|---|
| Base de connaissances | **Recherche automatique** à chaque question : les extraits (hybrid search, Top K) sont injectés d'office dans le prompt. | **Aucune injection.** Le modèle reçoit seulement la liste des bases disponibles, et doit appeler l'outil `query_knowledge_files`, qui fait partie des **Builtin Tools**. |
| Outils | Avant la réponse, un appel supplémentaire au modèle décide s'il faut utiliser un outil. | Les outils sont passés au modèle, qui les appelle pendant sa réponse. |
| Coût par question | Une recherche, plus un court appel de sélection si des outils sont attachés. | Au moins deux passes de génération dès qu'un outil est appelé, y compris pour lire la base. |
| Fiabilité avec un modèle de 8B | ✅ La recherche a toujours lieu. | ⚠️ Le modèle oublie souvent d'appeler l'outil et répond sans avoir lu les documents. |

> **Piège rencontré** : avec *Native* et *Builtin Tools* décoché, l'assistant n'a **aucun moyen** de lire sa base. Il répond « l'information n'est pas disponible », alors que les documents sont bien indexés et rattachés. Les logs ne montrent alors aucune recherche.
>
> À noter : une base appelée par `#` dans une conversation passe par un autre circuit, et elle est bien injectée même en Native. C'est pourquoi le test avec `#` fonctionnait alors que l'assistant échouait.

**Quel mode choisir :**

| Usage | Function Calling | Builtin Tools |
|---|---|---|
| Assistant documentaire (questions sur un corpus) | **Legacy** | ❌ |
| Documents + quelques outils, les documents restant la source principale | **Legacy** | ❌ |
| Agent qui choisit librement entre plusieurs outils et sources | Native | ✅ |

Sur la configuration de référence du tutoriel 01 (~14,5 tokens/s), le troisième cas est lent et peu fiable avec un modèle de 8B. Pour de vrais agents, préférez un workflow **n8n** (nœud AI Agent), où les étapes sont décrites explicitement, et exposez-le comme un simple outil (voir 4.1).

Gardez **Native** sur le modèle de base `granite4.2:8b` : il n'a pas de base rattachée, et ce mode est le plus efficace pour les outils.

---

## 6. Étape 4 : tester

Ouvrez une **nouvelle conversation** à chaque test, pour que l'historique d'un test précédent n'influence pas la réponse.

| Test | Avec | Attendu |
|---|---|---|
| Question sur les documents, **sans `#`** : « Quel est le rôle de Novaltis dans le Projet Héron ? » | Expert MBSE | Indication « recherche dans la base » pendant le traitement, réponse citée [n], sources affichées sous la réponse. |
| Information absente : « Quel est le coût de licence par poste ? » | Expert MBSE | Le modèle dit que l'information manque. |
| Question générale : « Différence entre SysML v1 et v2 en 5 points » | `granite4.2:8b` | Réponse tirée de ses connaissances, sans refus. |
| Demande qui nécessite un outil | Expert MBSE (avec outil) | L'outil est appelé (indiqué dans le statut), et son résultat est utilisé. |

La série complète de questions de test et le tableau de diagnostic figurent dans le [guide de configuration, §7](01-configuration-open-webui.md#7-tester-le-rag).

---

## 7. Vérifier par la ligne de commande

Les commandes ci-dessous sont à lancer depuis la racine du dépôt.

**L'assistant est-il bien configuré ?** La base est-elle rattachée, et le mode est-il Legacy ?

```bash
docker compose exec open-webui python3 -c "
import sqlite3, json
c = sqlite3.connect('/app/backend/data/webui.db')
for id, params, meta in c.execute('select id, params, meta from model where base_model_id is not null'):
    p, m = json.loads(params), json.loads(meta)
    print(id, '| function_calling =', p.get('function_calling'),
          '| knowledge =', [k.get('name') for k in (m.get('knowledge') or [])])
"
```

Un `knowledge = []` signifie que la sélection n'a pas été enregistrée : le cas se produit si l'on quitte l'écran sans cliquer sur *Save & Update*.

**Combien d'extraits par document ?** (remplacer l'identifiant par celui de la base)

```bash
docker compose exec postgres psql -U "$POSTGRES_USER" -d rag -c "
  SELECT vmetadata->>'name' AS fichier, count(*) AS extraits
  FROM document_chunk
  WHERE collection_name = '<id-de-la-base>'
  GROUP BY 1 ORDER BY 1;"
```

L'identifiant de la base figure dans l'URL de sa page (*Workspace → Knowledge → MBSE Expert*).

**La recherche a-t-elle eu lieu ?** Pendant une question, la longueur du prompt dans les logs d'Ollama doit dépasser quelques milliers de tokens (prompt système + ~8 extraits) :

```bash
docker compose logs -f ollama | grep -E 'new prompt|prompt eval'
```

Un prompt de quelques centaines de tokens signifie qu'aucun extrait n'a été injecté. Vérifiez alors le mode *Function Calling* (5.4) et la base rattachée.

---

## 8. Partager l'assistant

Chaque élément du Workspace (assistant, base, outil) a un réglage d'**accès** dans son écran d'édition : privé, partagé avec des groupes, ou public.

Pour qu'un collègue utilise l'assistant, il doit avoir accès **à l'assistant et à sa base** : un assistant partagé dont la base reste privée répondra sans documents.

---

## 9. Donner une mémoire à l'assistant : Notes et Memory

Un modèle ne se souvient de rien d'une conversation à l'autre. Open WebUI propose deux mécanismes pour lui fournir un contexte durable, qui répondent à deux besoins différents.

### 9.1 Notes

**Notes** (menu de gauche, au-dessus de *Workspace*) est un **bloc-notes Markdown** intégré :

| Fonction | Usage |
|---|---|
| Écrire et organiser | Éditeur Markdown, sauvegarde automatique, notes épinglables. |
| Améliorer avec l'IA | Faire reformuler, structurer ou résumer la note par le modèle. |
| Discuter de la note | Un panneau de chat à côté de la note : le modèle lit la note et ses fichiers joints. |
| Dicter | Enregistrer de l'audio et le faire transcrire. Par défaut, la transcription utilise Whisper sur le CPU du conteneur : c'est lent, et ce n'est pas testé sur cette stack. |
| Partager | Privée, ou partagée avec d'autres utilisateurs, comme les éléments du Workspace. |

**Une note n'est pas lue automatiquement dans les conversations.** Elle n'y entre que dans deux cas :

| Cas | Comment | Sur cette stack |
|---|---|---|
| On l'appelle | `#` dans le chat, puis choisir la note : son contenu est ajouté au contexte. | ✅ |
| Le modèle va la chercher | En Function Calling *Native* avec *Builtin Tools* activés, le modèle dispose des outils `search_notes` et `view_note`, et aussi de `write_note` et `replace_note_content` : il peut **modifier** vos notes. | ❌ Builtin Tools désactivés ; peu fiable avec un modèle de 8B |

> Le chat d'une note active les Builtin Tools même s'ils sont décochés sur le modèle : ses réponses sont un peu plus lentes que dans une conversation normale.

### 9.2 Memory

**Settings → Personalization → Memory** : on y enregistre de **courts faits** sur soi (« Je suis ingénieur MBSE, je travaille sur la migration SysML v2 », « Réponds en français »).

À chaque message, Open WebUI cherche les **8 souvenirs les plus proches** des derniers messages de l'utilisateur et les **injecte automatiquement** dans le contexte, dans la limite de **2 000 caractères**. Il faut pour cela que la capability *Memory* du modèle soit cochée.

Réglages globaux, stockés dans la table `config` de `webui.db` :

| Clé | Valeur | Effet |
|---|---|---|
| `memories.enable` | true | La fonction est disponible. |
| `memories.system_context.enable` | true | Les souvenirs sont injectés dans les conversations. |
| `memories.background_review.enable` | **false** | Le modèle n'extrait pas de lui-même de nouveaux souvenirs après les échanges. À laisser désactivé ici : cela ajouterait un appel au modèle après chaque réponse, soit 10 à 30 s de GPU occupé. |

> Sur un **assistant documentaire**, décochez la capability *Memory* : des souvenirs personnels injectés dans le contexte vont contre la consigne « answer only from the provided context ». Gardez-la sur le modèle généraliste.

### 9.3 Laquelle utiliser ?

| | **Memory** | **Notes** |
|---|---|---|
| Nature | Faits courts, une ligne chacun | Documents structurés |
| Utilisation | **Automatique**, dans chaque conversation | **Explicite**, par `#` |
| Taille | ~2 000 caractères injectés au maximum | Plusieurs pages |
| Idéal pour | Qui vous êtes, vos préférences, votre contexte permanent | L'état d'un projet, les décisions prises, une synthèse en cours |

Combinaison conseillée :

- **Memory** : 3 à 5 faits stables sur vous, utilisés par le modèle généraliste.
- **Une note par projet** comme mémoire de travail (« Synthèse SysML v2 : décisions, points ouverts »). Vous y reportez ce qu'une conversation avec l'assistant a produit d'utile, vous la retravaillez, puis vous la rappelez avec `#` quand vous reprenez le sujet.

| | Notes | Knowledge | Conversation |
|---|---|---|---|
| Contenu | Votre propre texte | Des documents existants | Un échange de questions et réponses |
| Modifiable | ✅ en continu | ❌ il faut remplacer le fichier | ❌ |
| Volume adapté | Une à quelques pages | Des dizaines de documents | — |

---

## 10. Récapitulatif

| Où | Réglage | Valeur |
|---|---|---|
| Admin → Models → `granite4.2:8b` | System Prompt | **vide** (modèle généraliste) |
| | think / max_tokens / temperature / Function Calling | Off / 2048 / 0.3 / Native |
| Admin → Documents | Top K (nombre d'extraits) | 8 |
| Workspace → Knowledge | documents | DOCX, une version par document |
| Workspace → Tools | outils Python | facultatif |
| Admin → Integrations | serveurs OpenAPI / MCP | facultatif |
| Workspace → Models → Expert MBSE | Base Model | `granite4.2:8b` |
| | System Prompt | consignes RAG |
| | think / max_tokens / temperature | Off / 2048 / 0.3 |
| | **Function Calling** | **Legacy** |
| | top_k (échantillonnage) | Default |
| | Knowledge | MBSE Expert (collection) |
| | Capabilities | File Upload, File Context, Citations, Status Updates |
| | Builtin Tools, Memory | décochés |
| Settings → Personalization → Memory | faits sur l'utilisateur | 3 à 5, pour le modèle généraliste |
| Admin (`config`) | `memories.background_review.enable` | false |
| Notes | une note par projet | rappelée par `#` |

### Pièges rencontrés

| Symptôme | Cause | Correctif |
|---|---|---|
| Le modèle de base refuse de répondre aux questions générales | Prompt « answer only from the context » posé sur le modèle de base | Déplacer le prompt dans un assistant du Workspace. |
| L'assistant dit que l'information manque, et les logs ne montrent aucune recherche | Function Calling en Native avec Builtin Tools décoché | Passer l'assistant en **Legacy**. |
| La base n'apparaît pas dans l'assistant | Sélection non enregistrée | *Select Knowledge*, vérifier l'étiquette, puis **Save & Update**. |
| « Top K = 8 » sans effet sur le nombre d'extraits | Réglé dans les Advanced Params (échantillonnage) au lieu de *Admin → Documents* | Remettre top_k sur Default dans l'assistant ; régler Top K dans *Documents*. |
| Extraits en double, réponses incohérentes | Le même document indexé en PDF et en DOCX | Ne garder que le DOCX. |
