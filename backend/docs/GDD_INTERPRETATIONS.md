# Points du GDD explicitement interprétés

Ce fichier existe pour éviter de transformer une ambiguïté du GDD en règle "inventée" sans le dire.

## 1. Timescale

Le GDD présente d'abord un exemple de timescale variable, puis définit ensuite un **standardized timescale = 5** et un tick de `0.2 s` réel pour `1 s` relatif. Le backend retient la règle standardisée : la logique travaille uniquement en ticks relatifs ; Godot est libre de jouer les animations à `0.2 s/tick` ou à une vitesse de replay différente.

## 2. `HACK_CUT`

La description d'Imahaki dit qu'un Grappler coupe automatiquement l'arbre quand il est dessus et qu'Imahaki doit simplement `WAIT`. Plus loin, la section batterie cite néanmoins `HACK_CUT` parmi les exemples d'actions consommant 1 point de batterie.

Décision :

- le moteur **accepte** `HACK_CUT` pour compatibilité ;
- la stratégie par défaut **ne l'émet pas** ;
- elle utilise `WAIT` quand un Grappler contrôlé se trouve sur un arbre.

## 3. Score d'exemple et temps restant

Le fichier exemple indique `TIME_LIMIT = 100`, le replay d'annexe contient 20 ticks, mais l'exemple numérique de score utilise `T = 100`. Ces trois éléments ne sont pas arithmétiquement compatibles si `T` signifie bien "remaining relative time to limit".

Décision : le backend applique littéralement la définition de `T` :

`remaining_time = max(0, time_limit - elapsed_ticks)`.

Le score local est donc une prévisualisation cohérente avec la formule, mais le score officiel reste celui du runner AlgoMada.

## 4. Nombre de lignes de `actions.txt`

Le GDD demande au maximum `TIME_LIMIT` lignes d'actions et impose `END_GAME` comme dernière ligne. Son propre exemple contient 20 paires d'actions puis `END_GAME` et le décrit comme 20 ticks.

Décision : au maximum `TIME_LIMIT` **paires d'actions**, puis une ligne terminale `END_GAME`.

## 5. Poussées simultanées

Le GDD précise explicitement que plusieurs agents poussant un même coffre dans des directions différentes bloquent le coffre et les agents. Il ne détaille pas le cas où plusieurs agents poussent exactement dans la même direction.

Décision locale :

- directions différentes : conflit, aucune poussée ;
- même direction : le coffre avance une seule fois et tous les pousseurs héros impliqués avancent sur son ancienne case.

Le planificateur évite volontairement ces conflits, donc cette interprétation sert surtout au replay/validation local.

## 6. Compteur des 5 pas de l'Excavator

La règle "dig every 5 steps" est décrite dans le bloc de comportement de l'Excavator **while not currently being hacked**.

Décision : seuls les mouvements automatiques font progresser le compteur de creusement. Les `HACK_MOVE` n'avancent pas ce compteur automatique.

## 7. Priorité de collecte simultanée héros/machine

Dans l'annexe, Imahaki et le Grappler arrivent tous les deux sur la pierre `(0,1)` au tick 2, et la pierre est créditée à Imahaki.

Décision : dans le simulateur local, les déplacements héros sont appliqués avant l'exécution des mouvements machines du même tick pour la collecte des pierres.

## 8. Hack et routines automatiques des machines

Clarification AlgoMada : `HACK` ne désactive pas toutes les actions automatiques.

Le moteur applique maintenant exactement la séparation suivante :

- le hack annule les mouvements automatiques de la machine ;
- le hack annule ses rotations automatiques ;
- sur un Excavator, le `DIG` périodique est suspendu tant qu'il est hacké ;
- sur un Grappler, le `CUT` automatique reste actif même sous contrôle d'Imahaki ;
- lorsqu'un Grappler contrôlé arrive sur un arbre, le tick suivant est réservé au `CUT` automatique, sans coût batterie de commande.

Le compteur de pas automatiques de l'Excavator n'est pas remis à zéro par le hack. Les déplacements `HACK_MOVE` ne l'incrémentent pas.

## 9. Machines adjacentes et déplacement en convoi

Des machines voisines orientées dans la même direction peuvent effectuer leur déplacement simultanément si toute la chaîne libère effectivement sa case pendant le tick d'exécution.

Le moteur résout donc les déplacements comme des intentions simultanées :

- une machine peut entrer dans la case actuellement occupée par une autre machine si celle-ci avance elle aussi pendant le même tick et avec la même orientation ;
- la règle s'étend à une chaîne de plusieurs machines ;
- si une machine intermédiaire ne libère pas sa case, toutes les machines bloquées derrière elle considèrent le chemin bloqué ;
- les machines automatiques bloquées appliquent alors leur rotation normale ;
- une machine hackée ne reçoit jamais une rotation automatique à cause de ce blocage.

## 10. Coffres entre machines

Les mouvements et poussées sont vérifiés avant application pour éviter qu'un coffre et une machine aboutissent sur la même case.

Sont notamment bloqués :

- une machine qui pousse un coffre vers une case contenant déjà une autre machine ;
- deux machines poussant le même coffre dans des directions différentes ;
- une machine qui avance vers la case où une autre machine va pousser un coffre pendant le même tick ;
- le motif du type `G.*X` avec orientations opposées conduisant la machine de gauche et le coffre vers la même case.

Dans ces cas, les machines automatiques concernées se réorientent au lieu d'effectuer le mouvement dangereux.

Un héros ne peut pas pousser un coffre vers une case occupée par une machine. Une case occupée par l'autre héros n'est pas considérée comme bloquante pour le coffre. La stratégie évite de demander aux deux héros de pousser le même coffre en même temps et attribue la poussée à un seul héros.

## 11. Tailles de cartes d'évaluation

La logique reste dynamique pour toute dimension valide. Deux cartes de validation supplémentaires sont incluses :

- `maps/mechanics_4x5.txt`, petite carte contenant tous les types d'éléments ;
- `maps/evaluation_10x14.txt`, dimension correspondant au double de la carte de référence `5x7`.

La stratégie adaptative et le simulateur sont exécutés automatiquement sur ces cartes dans la suite de tests.
