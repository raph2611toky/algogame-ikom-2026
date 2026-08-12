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
