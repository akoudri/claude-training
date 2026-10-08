# Outil d'obfuscation de documents — conception

Date : 2026-10-08

## Objectif

Outil en ligne de commande, en Python (géré par uv), qui obfusque des documents Word, Excel, PowerPoint et PDF
avant de les confier à Claude, puis restaure les termes réels dans les réponses.

Double usage :

- **professionnel** : préparer des documents réels (propositions, SOW, comptes rendus) ; la fiabilité prime ;
- **pédagogique** : démontré dans la formation Claude Code ; le code doit rester lisible.

## Décisions

| Sujet | Décision |
|---|---|
| Canal | Fichiers uniquement (pas de proxy entre Claude Code et l'API). Le moteur reste réutilisable pour un proxy ultérieur. |
| Réversibilité | Aller-retour complet via une table de correspondance locale, jamais envoyée. |
| Détection | Dictionnaires YAML + motifs regex intégrés. Pas de NER (spaCy/Presidio). |
| Remplaçants | Jetons explicites `[CATEGORIE_n]`. |
| Office | Même format en sortie, mise en forme préservée, traitement au niveau XML (lxml). |
| PDF | Converti en Markdown (`pymupdf4llm`), puis traité comme du texte. |
| Approche | Moteur maison. Presidio, LLM Guard et les services commerciaux ont été écartés (texte seul, dépendances lourdes, ou envoi des données à un tiers). |

## Utilisation

```bash
cd obfuscation && uv sync
uv run obfusquer documents/ -d dictionnaires/client.yaml [-d autre.yaml] -t client.table.json -o sortie/
uv run restaurer reponse.md -t client.table.json -o restaure/
pbpaste | uv run restaurer - -t client.table.json      # texte sur l'entrée standard, résultat sur la sortie standard
```

- `obfusquer` accepte des fichiers et des dossiers (parcours récursif, arborescence reproduite dans `-o`).
  Extensions traitées : `.docx`, `.xlsx`, `.pptx`, `.pdf`, `.md`, `.txt`. Les autres fichiers sont ignorés et signalés.
- `restaurer` accepte `.md`, `.txt`, `.docx`, `.xlsx`, `.pptx` ou `-` (entrée standard).
- Les noms de fichiers sont obfusqués (`Proposition Novaltis.docx` → `Proposition [CLIENT_1].docx`) et restaurés.
- Un PDF `contrat.pdf` produit `contrat.md`. Si ce nom est déjà pris dans la sortie, erreur pour ce fichier.

## Dictionnaires

```yaml
CLIENT:
  - [Novaltis, Novaltis SA, NVL]   # variantes : même jeton, restaurées vers la première
PROJET:
  - [Projet Héron, Héron, Heron]
PERSONNE:
  - [Jean Dupont, J. Dupont, M. Dupont]
  - Claire Martin                  # terme seul
motifs:                            # facultatif : regex propres au contexte
  CONTRAT: 'CTR-\d{6}'
```

- Catégorie : majuscules, chiffres et `_` (`^[A-Z][A-Z0-9_]*$`). `motifs` est réservé.
- Correspondance insensible à la casse, sur mots entiers (`(?<!\w)` … `(?!\w)`, pour accepter des termes finissant
  par un point comme `J. Dupont`). Les accents ne sont pas normalisés : déclarer les variantes sans accent.
- En cas de chevauchement, la correspondance la plus longue gagne, quelle que soit sa source ; à longueur égale,
  le dictionnaire prime sur les motifs. Ainsi `jeanne.martin@novaltis.example` devient `[EMAIL_1]` et non
  `jeanne.martin@[CLIENT_1].example`, qui laisserait fuir le nom.
- Plusieurs dictionnaires (`-d` répété) sont fusionnés.
- Erreurs bloquantes, signalées avant tout traitement avec fichier et ligne : YAML invalide, nom de catégorie
  invalide, même terme (casse ignorée) dans deux catégories, regex invalide.

### Motifs intégrés (toujours actifs)

`EMAIL`, `TELEPHONE` (formats français `0X XX XX XX XX` avec espaces, points ou tirets, et `+33`/international),
`IBAN` (validé par la clé modulo 97), `SIRET` (14 chiffres) et `SIREN` (9 chiffres), tous deux validés par Luhn,
`URL` (http/https), `IP` (IPv4). Chaque valeur distincte reçoit son propre jeton (`[EMAIL_1]`, `[EMAIL_2]`…).

## Table de correspondance

```json
{
  "version": 1,
  "jetons": {
    "[CLIENT_1]": "Novaltis",
    "[EMAIL_1]": "j.dupont@novaltis.fr"
  }
}
```

- Un terme de dictionnaire est associé à sa forme canonique (première variante) ; un motif, à la valeur trouvée.
- La table est chargée si elle existe et complétée : un même terme garde le même jeton d'une exécution à l'autre.
  La numérotation continue par catégorie.
- Écriture atomique (fichier temporaire puis renommage, droits `0600`) après chaque fichier produit, avant l'écriture
  du document : une interruption ne laisse aucun document impossible à restaurer. Une erreur de configuration arrête
  tout avant le premier fichier.
- L'outil refuse d'écrire la table dans le dossier de sortie. Le `.gitignore` exclut `*.table.json`.

## Restauration

- Reconnaît `[CLIENT_1]`, `\[CLIENT_1\]` (crochets échappés en Markdown) et `CLIENT_1` sans crochets, sur mot entier.
- Les jetons absents de la table sont signalés (avertissement, laissés tels quels).
- Les mêmes adaptateurs de formats servent dans les deux sens.

## Architecture

```
obfuscation/
├── pyproject.toml            # scripts : obfusquer, restaurer
├── README.md
├── src/obfuscation/
│   ├── dictionnaire.py       # chargement, validation, construction de la recherche
│   ├── motifs.py             # motifs intégrés et leurs validations (Luhn, modulo 97)
│   ├── table.py              # table de correspondance : chargement, attribution, sauvegarde atomique
│   ├── moteur.py             # remplacements(texte) -> [(debut, fin, remplacant)], dans les deux sens
│   ├── segments.py           # application des remplacements à un texte découpé en segments
│   ├── controle.py           # contrôle résiduel des fichiers produits
│   ├── cli.py
│   └── formats/
│       ├── ooxml.py          # zip, parcours des parties XML, recopie à l'identique du reste, récursion
│       ├── xml_texte.py      # unités de texte (Word, PowerPoint, Excel), passe générique, attributs
│       ├── excel.py          # formules, noms de feuilles, en-têtes, cellules numériques
│       ├── pdf.py            # PDF -> Markdown
│       └── texte.py          # .md / .txt
├── tests/
├── exemples/                 # dictionnaire du corpus fictif + generer.py
└── docs/specs/
```

### Moteur

`Moteur(dictionnaire, table)` expose `remplacements(texte, sens)`, qui renvoie la liste ordonnée et sans
chevauchement des `(debut, fin, remplacant)`. Les adaptateurs ne connaissent que cette interface, ce qui permet de
brancher plus tard un autre détecteur (Presidio) ou de réutiliser le moteur dans un proxy.

### Segments

Un paragraphe Office est une suite de segments de texte (`w:t`, `a:t`, `t`) portant chacun sa mise en forme.
`segments.py` concatène les textes, calcule les remplacements sur le texte complet, puis réécrit les segments :
le remplaçant est placé dans le premier segment touché, les segments suivants couverts par la correspondance sont
raccourcis (vidés si besoin). `xml:space="preserve"` est posé quand un segment commence ou finit par une espace.

### Formats Office (`ooxml.py` + règles)

Le fichier est ouvert comme un zip. Chaque partie XML (`.xml`, `.rels`, `.vml`) est analysée avec lxml et réécrite
si elle change ; toutes les autres entrées sont recopiées à l'identique (même contenu, même ordre). Une table commune
désigne les « unités de texte » (éléments dont les segments descendants forment un texte continu ; une zone de texte
imbriquée forme sa propre unité). Une passe générique traite ensuite tout autre élément portant du texte
(métadonnées, `w:instrText`, caches de graphiques…), sauf les valeurs numériques (`v` des cellules non textuelles,
caches numériques des graphiques). Attributs traités : `author`, `initials`, `descr`, `title`, `tooltip`,
`userName`, `name` de `cNvPr`/`docPr`, `displayName` de `person`, `val` de `tblCaption`/`tblDescription`, et la
cible des relations externes (liens `mailto:`, `https:`). Une partie `.vml` mal formée (fréquent dans Excel) est
recopiée telle quelle ; le contrôle résiduel la vérifie en texte brut.

- **Word** : toutes les parties `word/*.xml` contenant des paragraphes (document, en-têtes, pieds de page, notes de
  bas de page et de fin, commentaires) ; unité `w:p`, segments `w:t` et `w:delText` (texte supprimé des révisions),
  y compris dans les zones de texte et les liens hypertexte. Attributs `w:author` et `w:initials`.
- **Excel** : `xl/sharedStrings.xml` (unité `si`, segments `t`, texte enrichi compris), chaînes en ligne des
  feuilles (`is`), formules (`f`), commentaires, en-têtes et pieds de page (`headerFooter`), noms de feuilles
  (`sheet@name`) et noms définis (`definedName`). Les crochets étant interdits dans un nom de feuille, on y écrit le
  jeton nu (`CLIENT_1`), y compris dans les références des formules (`CLIENT_1!A1`), ce qui garde les formules
  valides ; à la restauration, un nom invalide (trop long, caractères interdits) est laissé tel quel avec un
  avertissement. Dans les en-têtes, les codes de mise en forme (`&C`, `&"Arial,Gras"`, `&12`…) sont isolés avant
  remplacement. Un nombre qui correspond entièrement à un motif (SIRET saisi comme nombre) devient une chaîne
  obfusquée.
- **PowerPoint** : diapositives, notes, masques et dispositions ; unité `a:p`, segments `a:t`. Graphiques
  (`a:t`, `c:v` des caches de texte).
- **Commun** : `docProps/core.xml` (titre, sujet, auteur, mots-clés, dernier modificateur, description) et
  `docProps/app.xml` (société, responsable). La miniature `docProps/thumbnail.*` est supprimée avec sa relation et
  sa déclaration de type.
- **Objets incorporés** : un `.docx`, `.xlsx` ou `.pptx` incorporé (`embeddings/`, données de graphiques) est traité
  récursivement. Les objets OLE binaires (`.bin`) et les images donnent lieu à un avertissement (nombre et
  emplacement) : leur contenu n'est pas traité.

### PDF

`pymupdf4llm.to_markdown(..., use_ocr=False)` produit le Markdown, ensuite traité comme du texte (sans
`use_ocr=False`, pymupdf4llm tente une OCR Tesseract si elle est installée). Un PDF sans couche texte
(texte extrait vide ou quasi vide) est une erreur pour ce fichier : pas d'OCR. Licence AGPL de PyMuPDF signalée
dans le README.

### Contrôle résiduel

Après l'obfuscation, chaque fichier produit est relu indépendamment des règles de format : pour un fichier Office,
toutes les parties XML (y compris des documents incorporés), tout le texte et toutes les valeurs d'attributs ; pour
un texte, tout le contenu. Les termes des dictionnaires et les valeurs déjà présentes dans la table y sont recherchés.
Si l'un d'eux subsiste, le fichier est renommé avec le préfixe `NON-CONFORME_`, les emplacements sont listés et
le code de retour est non nul.

## Gestion des erreurs

- Erreur de dictionnaire : arrêt avant tout traitement.
- Erreur sur un fichier (corrompu, PDF scanné, collision de nom) : fichier ignoré, message, poursuite, code de
  retour non nul en fin d'exécution.
- Avertissements (images, OLE, jetons inconnus à la restauration) : affichés, sans effet sur le code de retour.
- Codes de retour : 0 succès ; 1 au moins un fichier en erreur ou non conforme ; 2 erreur de configuration
  (dictionnaire, table, arguments).

## Tests

pytest, en TDD. Les fichiers Office de test sont générés par les tests (`python-docx`, `openpyxl`, `python-pptx`
en dépendances de développement uniquement), complétés par des retouches XML pour les cas piégeux. Aucun binaire
versionné.

- **Moteur** : terme le plus long prioritaire, mots entiers, casse, variantes, conflits de dictionnaires, chaque
  motif intégré (positifs et négatifs, clés de contrôle), aller-retour exact, restauration tolérante, jetons
  inconnus, numérotation continue d'une table rechargée.
- **Segments** : terme coupé sur deux ou trois segments, plusieurs termes par paragraphe, espaces en bord de segment.
- **Formats** : pour chaque format, le fichier produit s'ouvre avec la bibliothèque correspondante, aucun terme ne
  subsiste (recherche brute dans tout le zip), les images sont identiques octet pour octet, la restauration rend le
  texte d'origine. Cas dédiés : révision suivie, note de bas de page, commentaire, note du présentateur, onglet cité
  dans une formule, classeur incorporé dans un document Word, miniature supprimée.
- **Contrôle** : un fichier dont une partie a été volontairement oubliée est détecté et renommé `NON-CONFORME_`.
- **CLI** : codes de retour, refus d'écrire la table dans la sortie, noms de fichiers, entrée standard.

## Intégration dans le dépôt

- `obfuscation/README.md` (français) : installation, utilisation, dictionnaires, limites (texte dans les images,
  OLE binaires, OCR, AGPL), bonnes pratiques (la table ne quitte jamais la machine), démonstration de bout en bout.
- `obfuscation/exemples/` : `dictionnaire.yaml` pour le corpus fictif de `local-llm/n8n/exemples/` (Projet Héron,
  Novaltis) et `generer.py`, qui en produit un `.docx`, un `.xlsx`, un `.pptx` et un `.pdf` dans un dossier ignoré
  par git. Démonstration : obfusquer, demander une synthèse à Claude Code, restaurer.
- `CLAUDE.md` racine : présentation de `obfuscation/` et commande de test (`cd obfuscation && uv run pytest`).
- `.gitignore` : `obfuscation/.venv/`, `obfuscation/sortie/`, `obfuscation/exemples/generes/`, `*.table.json`,
  caches Python d'`obfuscation/`.
- Labs inchangés pour l'instant ; un éventuel exercice (lab M4, sécurité) sera décidé une fois l'outil livré.

## Hors périmètre

Proxy vers l'API, détection NER, remplaçants réalistes (Faker), PDF en sortie, OCR, anciens formats
(`.doc`, `.xls`, `.ppt`), texte dans les images.
