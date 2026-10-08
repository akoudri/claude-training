# Obfuscation de documents

Remplace les termes sensibles de documents Word, Excel, PowerPoint, PDF et texte par des jetons (`[CLIENT_1]`,
`[EMAIL_2]`…) avant de les confier à Claude, puis remet les termes réels dans les réponses. Tout se passe en local :
la table de correspondance entre jetons et termes ne quitte jamais la machine.

## Installation

```bash
cd obfuscation
uv sync
```

## Utilisation

```bash
# Obfusquer un dossier (ou des fichiers) : .docx, .xlsx, .pptx, .pdf, .md, .txt
uv run obfusquer documents/ -d mon-client.yaml -t ~/.obfuscation/mon-client.table.json -o sortie/

# Restaurer une réponse de Claude (fichier ou dossier)
uv run restaurer reponse.md -t ~/.obfuscation/mon-client.table.json -o restaure/

# Restaurer du texte collé (entrée standard → sortie standard)
uv run restaurer - -t ~/.obfuscation/mon-client.table.json < reponse.txt
```

- `-d` est répétable : plusieurs dictionnaires sont fusionnés.
- La table est créée au premier passage puis complétée : un même terme garde le même jeton d'un document et d'une
  exécution à l'autre. Une table par client ou par projet. Elle est enregistrée après chaque fichier, avec des
  droits de lecture réservés à son propriétaire.
- Les noms de fichiers et de dossiers sont obfusqués eux aussi (`Proposition Novaltis.docx` →
  `Proposition [CLIENT_1].docx`).
- Un PDF devient un fichier Markdown (`contrat.pdf` → `contrat.md`) : la mise en page est perdue, le texte est
  conservé.
- Codes de retour : `0` succès, `1` au moins un fichier en erreur ou non conforme, `2` erreur de configuration.

## Dictionnaires

```yaml
CLIENT:
  - [Novaltis, Novaltis SA, NVL]   # variantes : même jeton ; « restaurer » remet la première
PROJET:
  - [Projet Héron, Héron, Heron]   # déclarer les variantes sans accent
PERSONNE:
  - Jeanne Martin
motifs:                            # facultatif : expressions régulières propres au contexte
  CONTRAT: 'CTR-\d{6}'
```

- Catégories en majuscules (`A-Z`, chiffres, `_`). Un même terme ne peut pas figurer dans deux catégories.
- La recherche ignore la casse, accepte n'importe quelles espaces entre les mots, reconnaît les accents composés
  comme décomposés et les apostrophes ou tirets typographiques (`L’Oréal` pour `L'Oréal`). Un terme est délimité
  par tout ce qui n'est pas une lettre : `Novaltis_2026` et `dossier_Novaltis` sont reconnus, `NVLX` ne l'est pas.
- Quand deux correspondances se chevauchent, la plus longue l'emporte ; si elles ne se recouvrent qu'en partie,
  elles sont fusionnées sous un seul jeton pour que rien ne reste en clair.

Motifs intégrés, toujours actifs : `EMAIL`, `URL`, `TELEPHONE`, `IBAN` (clé vérifiée), `SIRET` et `SIREN`
(clé de Luhn vérifiée), `IP`.

## Ce qui est traité

- **Word** : corps, tableaux, en-têtes et pieds de page, notes, commentaires, zones de texte, texte supprimé des
  révisions, noms des relecteurs, textes de remplacement des images, champs et liens externes.
- **Excel** : cellules, commentaires, en-têtes et pieds de page, noms de feuilles (jeton sans crochets, interdits
  dans un nom de feuille : `CLIENT_1`) et formules qui les citent, nombres qui sont des SIRET ou des téléphones.
- **PowerPoint** : diapositives, notes, masques et dispositions, graphiques.
- **Partout** : métadonnées (auteur, titre, société…), images SVG, documents incorporés (un classeur dans un
  document Word, les données d'un graphique). La miniature d'aperçu, qui montre la première page en clair, est
  supprimée.

Après chaque obfuscation, un **contrôle** relit le fichier produit, indépendamment des règles ci-dessus, et y
cherche tous les termes des dictionnaires, toutes les valeurs de la table et les motifs (e-mail, IBAN, SIRET,
téléphone…), y compris dans le nom du fichier. Si quelque chose subsiste, le fichier est préfixé `NON-CONFORME_`,
les emplacements sont listés et la commande renvoie `1` : ne pas l'envoyer.

## Limites

- Le texte contenu dans les **images matricielles** (PNG, JPEG…) n'est pas traité : un avertissement indique leur
  nombre.
- Les **objets incorporés binaires** (OLE `.bin`) ne sont pas traités : avertissement, et le contrôle y cherche
  quand même les termes.
- Pas d'**OCR** : un PDF scanné, sans couche texte, est refusé.
- Formats anciens (`.doc`, `.xls`, `.ppt`) non pris en charge : les enregistrer d'abord au format actuel.
- Le dictionnaire ne trouve que ce qu'il contient : relire les documents obfusqués avant de les envoyer.
- **Licence** : la conversion PDF repose sur PyMuPDF, sous licence AGPL. Usage interne sans contrainte ; à
  vérifier avant toute redistribution de l'outil.

## Bonnes pratiques

- Ranger les tables **hors du dossier de travail** de Claude Code (par exemple `~/.obfuscation/`) et en interdire
  la lecture dans `.claude/settings.json` :

  ```json
  { "permissions": { "deny": ["Read(~/.obfuscation/**)"] } }
  ```

- L'outil refuse d'écrire la table dans le dossier de sortie. Les fichiers `*.table.json` sont exclus de git.
- Ne donner à Claude que le dossier de sortie, **copié hors de l'arborescence des originaux** : lancé dans
  `sortie/`, Claude Code voit aussi les dossiers voisins.

## Démonstration avec le corpus fictif

```bash
uv run python exemples/generer.py      # documents Office et PDF tirés de local-llm/n8n/exemples/
uv run obfusquer exemples/generes -d exemples/dictionnaire.yaml -t ~/.obfuscation/heron.table.json -o sortie
ls sortie                              # noms obfusqués : « Proposition [PRESTATAIRE_1] – [PROJET_1].docx »…
```

Copier ensuite `sortie/` dans un dossier isolé et y lancer Claude Code :

```bash
cp -r sortie /tmp/heron && cd /tmp/heron
claude -p "Résume le cahier des charges : liste les exigences et leurs livrables." > synthese.md
cd - && uv run restaurer /tmp/heron/synthese.md -t ~/.obfuscation/heron.table.json -o restaure
```

`synthese.md` ne contient que des jetons ; `restaure/synthese.md` contient les vrais noms.

Claude Code lit directement les fichiers Markdown (dont les PDF convertis), mais son outil de lecture n'ouvre pas
les `.docx`, `.xlsx` et `.pptx` : il propose alors une commande d'extraction (`unzip`, script Python), qu'il faut
approuver en session interactive. En mode `claude -p`, sans approbation possible, il s'arrête et le signale. Les
documents Office obfusqués peuvent aussi être déposés tels quels dans claude.ai.

## Développement

```bash
uv run pytest
```

Les documents de test sont fabriqués par `tests/documents.py` : aucun fichier binaire n'est versionné.
Conception : `docs/specs/2026-10-08-obfuscation-design.md` ; plan : `docs/plans/2026-10-08-obfuscation.md`.
