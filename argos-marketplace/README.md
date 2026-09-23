# Marketplace de démonstration — Argos

Marketplace Claude Code utilisée en extension du lab M2. Elle contient un plugin,
`argos-toolkit`, qui ajoute à la session :

| Élément             | Type      | Effet                                                        |
| ------------------- | --------- | ------------------------------------------------------------ |
| `/argos-toolkit:changelog` | skill | Changelog des commits non publiés (Conventional Commits) |
| `test-runner`       | sub-agent | Lance `npm test` et résume les échecs                        |
| rappel au démarrage | hook `SessionStart` | Rappelle la convention de casse des statuts       |

## Installation

Depuis une session Claude Code ouverte dans `argos/` :

```text
/plugin marketplace add ../argos-marketplace
/plugin install argos-toolkit@janus-argos
```

Si la marketplace est publiée sur GitHub : `/plugin marketplace add <organisation>/argos-marketplace`.

Redémarrer la session (ou `/reload-plugins`) puis vérifier avec `/plugin` (onglet *Installed*),
`/agents` et `/help`. Désinstallation : `/plugin uninstall argos-toolkit@janus-argos`.
