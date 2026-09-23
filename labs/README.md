# Labs — Formation Claude Code

Les six labs suivent un fil rouge unique : **Argos**, un petit gestionnaire de tickets
volontairement imparfait. Chaque lab part de l'état laissé par le précédent.

| Lab | Titre | Ce qu'Argos y gagne | Module |
| --- | ----- | ------------------- | ------ |
| [M1](lab-m1.md) | Premiers pas sur Argos | Bug de filtrage des statuts corrigé | Prise en main |
| [M2](lab-m2.md) | Consigner Argos | CLAUDE.md, commande `/audit-statuts`, hook | Configuration et personnalisation |
| [M3](lab-m3.md) | Livrer les commentaires sur ticket | Commentaires livrés par une équipe d'agents | Sub-agents et équipes d'agents |
| [M4](lab-m4.md) | Fermer la faille | Clé sortie du code, sandbox, allowlist réseau | Sécurité |
| [M5](lab-m5.md) | Reproduire Argos | Devcontainer et Codespace | Environnements reproductibles |
| [M6](lab-m6.md) | Construire la recherche | Recherche par mot-clé en TDD | Aller plus loin |

Chaque lab comporte un **socle** (pour tous) et une **extension** (pour aller plus loin), une
liste de pièges et le livrable attendu.

## Préparer son poste (avant le jour 1)

| Outil | Version | Vérification | Utile pour |
| ----- | ------- | ------------ | ---------- |
| Node.js | 22.13 ou plus récent | `node --version` | tous les labs (Argos) |
| Git | récent | `git --version` | tous les labs |
| Claude Code | dernière version | `claude --version`, `claude doctor` | tous les labs |
| Compte Claude (Pro, Max, Team ou Enterprise) ou Console | — | `claude` puis connexion | tous les labs |
| VS Code ou JetBrains | récent | — | extension M1, M5 |
| Docker + extension Dev Containers | récent | `docker run hello-world` | M5 |
| Compte GitHub avec Codespaces | — | github.com/codespaces | M5 |
| Linux / WSL2 : `bubblewrap` et `socat` | — | `which bwrap socat` | M4 (sandbox) |

Windows : les labs M4 et M5 supposent WSL2 (le sandbox de Claude Code n'existe pas sous Windows
natif). Installer Node, Git et Claude Code dans la distribution WSL2.

Installation de Claude Code (au choix) :

```bash
curl -fsSL https://claude.ai/install.sh | bash   # macOS, Linux, WSL2 (recommandé)
brew install --cask claude-code                  # macOS, Homebrew
winget install Anthropic.ClaudeCode              # Windows
npm install -g @anthropic-ai/claude-code         # toute plateforme avec Node.js
```

## Récupérer Argos

```bash
git clone <URL fournie par le formateur> argos
cd argos
npm install
npm test      # deux tests échouent au départ : c'est le bug du lab M1
npm run dev   # interface sur http://localhost:5173, API sur http://localhost:3000
```

## Se resynchroniser entre deux modules

En retard sur un lab ? Le formateur met à disposition l'état attendu en fin de chaque module
(`checkpoint/m1` à `checkpoint/m6`). Pour repartir de l'état de fin du module M2, par exemple :

```bash
git stash -u                                        # mettre son travail de côté
git fetch formateur checkpoint/m2                   # remote communiqué par le formateur
git switch -c reprise-m3 FETCH_HEAD
npm install
```
