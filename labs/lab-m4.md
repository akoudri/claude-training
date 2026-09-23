# Lab M4 — Fermer la faille

## Contexte

La fonctionnalité de commentaires est livrée depuis le lab M3, mais personne n'a encore regardé
ce que les agents pouvaient réellement atteindre pour la construire. Deux problèmes dorment dans
Argos : la clé du service de notification est écrite en clair dans le code, et rien ne limite
l'accès réseau à un domaine plutôt qu'un autre. Ce lab ferme les deux.

## Prérequis

- Argos avec la fonctionnalité de commentaires livrée et testée (lab M3).
- Avoir lu les notions de mode de permission, sandbox et allowlist réseau vues en module.
- Un accès en écriture à `.claude/settings.json` du dépôt.
- Le sandbox de Claude Code fonctionne sous macOS (rien à installer), Linux et WSL2 (paquets
  `bubblewrap` et `socat`). Il n'existe pas sous Windows natif : y utiliser WSL2. La commande
  `/sandbox` indique ce qui manque.
- Le service de notification réel (`api.notifications-argos.example`) est fictif : on travaille
  avec le faux service local, `npm run notif:mock`, et `NOTIF_API_URL=http://localhost:4010`.

## SOCLE — pour tous

1. **Localiser la clé en clair**
   Faire chercher par l'agent toute valeur qui ressemble à une clé d'API codée en dur dans le
   dépôt, sans lui donner l'emplacement à l'avance.
   - [ ] La clé du service de notification est identifiée sans indication préalable.

2. **Sortir la clé du code**
   Remplacer la valeur en clair par une lecture depuis une variable d'environnement
   (`NOTIF_API_KEY`), renseignée dans `.env` (non versionné) et documentée dans CLAUDE.md et
   `.env.example`. Le faux service accepte toute clé de la forme `ntf_test_` suivie d'au moins
   huit caractères alphanumériques.
   - [ ] Le code ne contient plus aucune valeur de clé en clair.
   - [ ] La fonctionnalité de notification continue de fonctionner avec la variable d'environnement
     renseignée localement.

3. **Configurer le sandbox**
   Activer le sandbox (`"sandbox": { "enabled": true, … }` dans `.claude/settings.json`, ou
   `/sandbox`) et ajouter une restriction filesystem qui interdit l'écriture sur `./migrations`
   et `./.env` (`sandbox.filesystem.denyWrite`). Le sandbox s'applique aux commandes shell
   lancées par Claude et à leurs sous-processus ; les outils d'édition de Claude (`Edit`,
   `Write`) relèvent, eux, des règles de permission : compléter avec
   `"permissions": { "deny": ["Read(/.env)", "Edit(/.env)"] }`.
   - [ ] Une commande shell qui tente d'écrire dans ces chemins (par exemple
     `echo x >> migrations/001_create_tickets.sql`) échoue sur une erreur du sandbox, même
     hors du hook posé en M2.
   - [ ] Une tentative de lecture de `.env` par Claude est refusée par la règle de permission.

4. **Restreindre le réseau**
   Ajouter une allowlist réseau (`sandbox.network.allowedDomains`) limitée aux domaines
   strictement nécessaires au fonctionnement d'Argos (registre de paquets, service de
   notification). Sous macOS, ajouter `"allowLocalBinding": true` pour que les tests (qui
   ouvrent un port local) tournent dans le sandbox.
   - [ ] Une tentative d'accès à un domaine hors de cette liste (par exemple
     `curl https://example.com`) n'aboutit pas sans accord explicite : Claude Code demande
     l'autorisation, et la refuser bloque l'accès.
   - [ ] Pour un refus sans question, relancer avec
     `claude --settings '{"sandbox":{"network":{"strictAllowlist":true}}}'` et constater le
     blocage direct. Ce réglage n'est pas pris en compte dans le `.claude/settings.json` du
     dépôt (seulement dans les réglages utilisateur, gérés ou `--settings`).
   - [ ] Les opérations normales (installation de dépendances, envoi d'une notification) continuent
     de fonctionner.

5. **Vérifier sans régression**
   Relancer la suite de tests complète et rejouer un ajout de commentaire de bout en bout.
   - [ ] Les tests passent toujours après la mise en place du sandbox et de l'allowlist.

## EXTENSION — pour aller plus loin

- Faire en sorte que la clé n'apparaisse jamais en clair dans les journaux de session : dans les
  réglages **utilisateur** (`~/.claude/settings.json` ; le masquage est ignoré dans les réglages
  du dépôt), déclarer `NOTIF_API_KEY` dans `sandbox.credentials.envVars` avec `"mode": "deny"`
  (variable retirée des commandes sandboxées) ou `"mode": "mask"` (valeur factice, substituée
  par le proxy du sandbox vers les seuls hôtes `injectHosts`, avec `network.tlsTerminate`).
  Vérifier avec une commande `env | grep NOTIF` lancée par Claude.
- Recenser les serveurs MCP actuellement connectés à la session Argos et désactiver ceux qui ne
  sont pas strictement nécessaires à la formation.
- Faire évaluer par l'agent, une fois le sandbox et l'allowlist en place, si le mode de permission
  utilisé jusqu'ici sur Argos reste approprié ou s'il devrait être resserré.

## Pièges & indices

- Une allowlist qui autorise un domaine générique trop large (par exemple un domaine parent au
  lieu du sous-domaine précis du service) revient à ne pas restreindre grand-chose : vérifier la
  précision de chaque entrée.
- Oublier de retirer la clé de l'historique Git après l'avoir retirée du code laisse la faille
  accessible à quiconque clone le dépôt : ce lab ne couvre pas la réécriture d'historique, mais le
  risque doit être nommé, pas ignoré. En situation réelle, la première action est de révoquer la
  clé exposée et d'en émettre une nouvelle.
- Avec `Read(/.env)` refusé, un `npm start` lancé par Claude dans le sandbox démarre sans la
  clé (notifications désactivées, avec un avertissement) : c'est voulu. Lancer l'application
  soi-même, dans son propre terminal, pour tester l'envoi de notifications.
- Dans les règles de permission, `/chemin` est relatif à la racine du projet et `//chemin` est
  absolu ; dans `sandbox.filesystem`, `./chemin` est relatif au projet et `/chemin` absolu. Ne
  pas mélanger les deux conventions.
- Un sandbox configuré puis jamais testé peut sembler fonctionner alors qu'il bloque une action
  légitime découverte seulement plus tard : toujours vérifier après configuration, pas seulement
  avant.

## Livrable

Un dépôt Argos sans secret en clair, avec un sandbox filesystem restrictif et une allowlist
réseau limitée au strict nécessaire, tests au vert. Ce dépôt durci sert de point de départ au
lab M5, qui vérifie qu'il se reproduit à l'identique en devcontainer et en Codespace.
