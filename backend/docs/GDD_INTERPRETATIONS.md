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

## 9. Buffer entre machines

Clarification AlgoMada la plus récente : les machines ne doivent jamais se déplacer de manière à devenir voisines. Le déplacement en convoi précédemment envisagé est abandonné.

Le moteur applique désormais les règles suivantes, indépendamment de l'orientation ou de l'état hacké de l'autre machine :

- si une autre machine occupe la case immédiatement devant, le MOVE est refusé ;
- si une autre machine se trouve à deux cases devant, avec une seule case libre entre les deux machines, le MOVE est refusé ;
- une machine automatique bloquée par ce buffer applique sa rotation normale ;
- une machine hackée bloquée par ce buffer refuse simplement `HACK_MOVE`, ne tourne pas automatiquement et ne dépense pas de batterie ;
- le fait que la machine devant puisse elle-même avancer au même tick ne supprime pas le buffer ; les convois ne sont plus autorisés.

Ainsi, pour `...G.X..`, si `G` regarde vers la droite, `G` se réoriente même si `X` regarde également vers la droite. Un héros n'est pas concerné par ce buffer : dans `...G.F..`, le Grappler peut avancer vers Ikotofosa.

## 10. Buffer coffre + machine

Un second buffer protège les situations où un coffre se trouve entre deux machines.

Pour un déplacement dans une direction donnée, si une autre machine se trouve à trois cases devant et qu'un coffre occupe la première ou la deuxième case de cette ligne, le MOVE est refusé. Cette règle couvre notamment `..G.*X` avec `G` orienté à droite et `X` orienté à gauche : les deux machines automatiques se réorientent au lieu d'avancer.

Cette règle s'applique aussi aux machines hackées : un `HACK_MOVE` qui violerait le buffer est transformé en `WAIT`, sans consommation de batterie et sans rotation automatique.

Les protections précédentes restent actives :

- une machine ne pousse pas un coffre vers une case contenant une autre machine ;
- deux machines ne poussent pas un même coffre dans des directions opposées ;
- une machine ne peut pas entrer dans la destination simultanée d'un coffre ;
- un héros ne peut pas pousser un coffre vers une case occupée par une machine ;
- une case occupée par l'autre héros reste autorisée pour le coffre ;
- la stratégie choisit un seul héros lorsque les deux pourraient pousser le même coffre.

## 11. Tailles de cartes d'évaluation

La logique reste dynamique pour toute dimension valide. Deux cartes de validation supplémentaires sont incluses :

- `maps/mechanics_4x5.txt`, petite carte contenant tous les types d'éléments ;
- `maps/evaluation_10x14.txt`, dimension correspondant au double de la carte de référence `5x7`.

La stratégie adaptative et le simulateur sont exécutés automatiquement sur ces cartes dans la suite de tests.
