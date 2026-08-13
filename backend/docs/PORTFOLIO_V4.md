# portfolio_v5

`portfolio_v5` applique une hiérarchie d'objectifs déterministe.

1. Chercher les coffres sécurisables immédiatement et prendre le plan direct le moins coûteux en ticks/stamina.
2. Pour chaque coffre restant, tester d'abord sa faisabilité structurelle en retirant uniquement les obstacles modifiables (`o`, `t`). Un coffre qui reste impossible dans cet état n'entraîne aucun hack inutile.
3. Identifier les obstacles réellement nécessaires au chemin du coffre. Les trous sont assignés à Ikotofosa + Excavator ; les arbres à Imahaki + Grappler.
4. Résoudre les dépendances croisées : si un Excavator ne peut atteindre un trou à cause d'arbres, Imahaki/Grappler les dégagent d'abord ; l'inverse est appliqué pour un Grappler bloqué par des trous.
5. Prépositionner/hacker une machine utile lorsqu'il faut la neutraliser pendant que le partenaire ouvre son corridor.
6. Après ouverture, sécuriser le coffre avant de changer de classe d'objectif.
7. Quand aucun coffre encore présent n'est sécurisable, collecter les pierres libres puis récupérer les pierres portées par les machines.

Le planner évite de hacker une machine sans objectif de coffre ou de récupération de pierre démontrable.

## Cas de régression 10x14

Le coffre en `(9,1)` de `user_impossible_bottom_chest_10x14.txt` est marqué non sécurisable : il se trouve sur la dernière ligne. Pour le pousser vers le haut, un pousseur devrait occuper la ligne 10, hors carte. Le déplacement horizontal ne peut pas rejoindre la cachette `(2,10)` et le rocher `(9,7)` ferme en plus le corridor inférieur. Remplir les trous ne change donc pas cette impossibilité géométrique.
