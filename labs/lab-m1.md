# Lab M1 — Premiers pas sur Argos

## Contexte

Argos est le fil rouge de la formation : un gestionnaire de tickets minimal (API + interface +
tests), volontairement imparfait. Ce premier lab installe l'outil, effectue la toute première
session guidée, et corrige le bug d'ouverture du projet.

Le bug : la liste des tickets « ouverts » affiche aussi des tickets déjà fermés. L'import
historique a enregistré certains statuts avec une majuscule (`Closed` au lieu de `closed`), et le
filtre côté API compare les chaînes de façon sensible à la casse. Résultat : ces tickets passent
le filtre alors qu'ils ne devraient pas apparaître.

Ce lab ne demande aucune connaissance préalable d'Argos : la première tâche consiste justement à
le découvrir avec l'agent plutôt que de lire le code seul.

## Prérequis

- Node.js 22.13 ou supérieur installé sur le poste : c'est ce qu'exige Argos (base SQLite
  intégrée à Node, voir `.nvmrc`). L'installeur natif de Claude Code, lui, n'a pas besoin de
  Node ; seule l'installation par npm en demande une version récente.
- Git installé.
- Un compte Claude actif (ou accès Console / fournisseur cloud de l'entreprise) pour
  l'authentification.
- Le dépôt `argos` cloné localement (URL fournie par l'équipe pédagogique en début de session),
  puis `npm install` exécuté une fois dans `argos/`.
- Aucun livrable de lab précédent : c'est le point de départ du fil rouge.

## SOCLE — pour tous

1. **Installer Claude Code**
   Choisir une méthode d'installation vue en module (npm, script natif, ou gestionnaire de
   paquets) et l'exécuter.
   - [ ] `claude doctor` confirme une installation fonctionnelle.

2. **S'authentifier**
   Lancer `claude` dans un terminal, suivre le flux de connexion ouvert dans le navigateur, puis
   revenir au terminal.
   - [ ] La session démarre sans erreur d'authentification.

3. **Se placer dans le dépôt Argos**
   Ouvrir un terminal dans le dossier `argos/` puis lancer `claude`. Accepter la demande de
   confiance du dossier (« trust ») à la première ouverture.
   - [ ] La session s'ouvre avec `argos/` comme répertoire de travail.
   - [ ] Dans un second terminal, `npm run dev` lance l'application : interface sur
     http://localhost:5173, API sur http://localhost:3000.

4. **Faire explorer le projet par l'agent**
   Demander une vue d'ensemble du projet avant toute modification : structure des dossiers, rôle
   de l'API, de l'interface, des tests.
   - [ ] L'agent restitue une description cohérente de l'architecture d'Argos, sans avoir modifié
     aucun fichier à ce stade.

5. **Faire diagnostiquer le bug**
   Décrire le symptôme observé (des tickets fermés apparaissent dans la liste des tickets
   ouverts) sans donner la cause, et demander à l'agent de localiser l'origine du problème.
   - [ ] L'agent identifie la comparaison de statut sensible à la casse comme cause probable,
     avant toute correction.

6. **Valider un plan avant d'agir**
   Demander un plan de correction avant exécution : quels fichiers seront modifiés, quelle est
   l'approche (normaliser la casse à l'import, ou au filtrage).
   - [ ] Un plan est proposé et relu avant d'autoriser l'exécution.

7. **Corriger et vérifier**
   Autoriser l'agent à appliquer la correction, puis faire relancer la suite de tests.
   - [ ] La suite de tests passe intégralement.
   - [ ] La liste des tickets ouverts n'affiche plus de tickets fermés.

## EXTENSION — pour aller plus loin

- Reproduire la même session dans un second point d'entrée (VS Code ou JetBrains) sur une copie du
  dépôt, et comparer l'expérience avec le terminal : affichage des diffs, gestion des permissions,
  confort d'usage.
- Faire annuler la correction via un checkpoint, puis la refaire en demandant cette fois une
  correction à l'import plutôt qu'au filtrage, et comparer les deux approches avec l'agent
  (avantages, inconvénients, effets de bord sur les données existantes).
- Demander à l'agent d'identifier si d'autres champs du projet pourraient souffrir du même défaut
  de normalisation (autres comparaisons de chaînes sensibles à la casse).

## Pièges & indices

- Un plan qui propose de modifier des fichiers de test en plus du code de production est un signal
  d'alerte : demander pourquoi avant d'accepter.
- Une commande refusée par les permissions n'est pas une panne : c'est le comportement attendu vu
  en module. Lire le message de refus avant de changer de mode.
- Corriger uniquement l'affichage (masquer les tickets « Closed » côté interface) sans toucher au
  filtre de l'API est une correction du symptôme, pas de la cause : le lab n'est pas validé tant
  que le filtre lui-même n'est pas corrigé.
- Si l'agent propose d'emblée la correction sans être passé par une étape de diagnostic explicite,
  demander de refaire en explicitant d'abord la cause : c'est l'objet du lab, pas seulement le
  résultat.
- Au départ, `npm test` affiche deux tests en échec : ils décrivent le comportement attendu et
  doivent passer au vert sans être modifiés.
- Les compteurs de l'en-tête ne tombent pas juste non plus (leur somme ne fait pas le total) : c'est
  un symptôme voisin, gardé pour l'extension et pour la commande `/audit-statuts` du lab M2.
- Le checkpoint (`/rewind`, ou `Échap` deux fois) annule les éditions faites par les outils de
  Claude, pas les effets des commandes shell (un `sed -i`, un `git checkout`…).

## Livrable

Un dépôt Argos avec le filtre de statut corrigé, la suite de tests au vert, et un historique de
session (ou une note courte) expliquant la cause du bug telle que diagnostiquée par l'agent. Ce
dépôt corrigé sert de point de départ au lab M2, qui y ajoute CLAUDE.md, une commande et un hook.
