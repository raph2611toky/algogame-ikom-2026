# Portfolio V14 — Global Mission AI

Version backend : **0.14.0**

## Objectif

V14 conserve `Rules`, `Simulator`, le Look Ahead officiel, l'élévation et les protections V12/V13 comme source de vérité. La nouveauté est une couche de planification de missions qui cherche non seulement **comment** atteindre une cible, mais **quelle combinaison de missions F + M maximise le score futur**.

## 1. Missions concurrentes sur la même échelle

À chaque replan, chaque héros peut produire plusieurs familles de candidats :

- coffre directement poussable par le héros ;
- coffre nécessitant volontairement son type de machine compatible ;
- pierre libre ;
- pierres déjà portées par une machine.

Il n'existe plus de phase globale « pierres d'abord ». Un coffre peut donc être préféré même s'il reste beaucoup de pierres.

V14 évalue en quarts de point de score :

```text
coffre sécurisé = +600
pierre           = +100
tick              =   -2
stamina           =   -1
battery           =   -1
```

À cela s'ajoutent les risques structurels et une pénalité de réserve de stamina qui devient forte sous 20 puis sous 10 points. Cette pénalité n'altère jamais la formule officielle : elle sert uniquement à éviter une stratégie qui vide un héros avant les objectifs les plus rentables.

## 2. MachineChestPlanner

`app/engine/machine_chest_planner.py` ajoute la capacité absente de V13 : **utiliser intentionnellement une machine pour pousser un coffre**.

Un noeud de recherche contient :

```text
(machine_position, machine_orientation, chest_position)
```

Pour chaque direction de poussée candidate :

1. déterminer la cellule derrière le coffre ;
2. utiliser le planner machine existant pour rejoindre cette cellule ;
3. orienter la machine ;
4. valider terrain, élévation machine, élévation du coffre, arbre/trou/rocher/autre coffre ;
5. valider la destruction éventuelle par falaise ;
6. ajouter le `HACK_MOVE` + tick d'attente du MOVE machine ;
7. continuer jusqu'à ce que le coffre atteigne un bush.

Le planner peut produire un plan structurel même si une autre machine crée actuellement un blocage Look Ahead transitoire. L'exécution V14 réapplique ensuite `Rules.machine_forward_queueable()` au tick réel ; elle attend/replanifie si la situation dynamique a changé.

## 3. Allocation simultanée F + M

V14 ne choisit plus F puis M de manière purement gloutonne. Il construit les meilleurs candidats de F et de M, puis compare les couples valides.

Pour un couple de missions, il prend en compte :

- somme des utilités ;
- gain du temps parallèle (`min(ticks_F, ticks_M)`) ;
- conflit sur le même coffre ;
- conflit sur la même machine ;
- chevauchement géographique inutile ;
- dépendances déjà réservées par une mission active.

Cela permet à F et M de travailler dans deux régions différentes lorsque c'est rentable, tout en laissant V13 gérer les cas de coopération/déblocage qui ne sont pas encore représentés par une mission V14.

## 4. Coffre mobile = identité mobile

Un coffre n'est pas identifié uniquement par sa coordonnée initiale. Chaque engagement mémorise `expected_chest` et, lors d'un MOVE machine à deux ticks, `pending_chest_to`.

Ainsi :

- si F pousse le coffre de `(r,c)` à `(r,c+1)`, M ne pense pas que l'ancien `(r,c)` est un nouveau coffre libre ;
- si un autre coffre est sécurisé ailleurs, cela ne termine pas prématurément cette mission ;
- si le MOVE machine est annulé au deuxième tick, la position attendue n'est pas appliquée et le plan est reconstruit.

## 5. Ressources et stamina

Pour une mission directe, V14 estime le besoin de stamina et le coût d'un éventuel WAIT de récupération. Pour une mission machine, les ticks passés à contrôler la machine sont aussi considérés comme une opportunité de récupération/préservation de stamina.

L'objectif n'est pas de conserver arbitrairement 100 de batterie : si dépenser 10 points de batterie permet de sécuriser un coffre de 150 points ou d'éviter une traversée très coûteuse en stamina, la mission devient normalement rentable.

## 6. Prévision des machines

Lorsqu'une machine compatible bouge de manière autonome, V14 peut faire un rollout court sur une copie profonde de l'état en utilisant le `Simulator` de production. Il cherche une future position de la machine que le héros peut intercepter dans la même fenêtre temporelle.

Le forecast est borné pour rester utilisable sur les cartes moyennes.

## 7. Release sûr

Si une mission machine devient impossible ou dépasse son budget de replans, V14 ne libère pas aveuglément la machine lorsque son orientation la ferait pousser immédiatement le coffre au tick suivant. Une rotation sûre est demandée avant l'abandon lorsque nécessaire.

## 8. Tailles de carte

Le service applique :

```text
<=160 cellules   V14 + comparaison exacte V13, meilleur résultat conservé
161..400         V14 medium_mode borné
>400 / stress    scalable_v1 borné, mais sans gate « pierres d'abord »
```

La limite `160` de V13 ne coupe donc plus l'IA globale sur une carte 15x20 (300 cellules).

## 9. Filets de sécurité conservés

V14 hérite de V13. Si aucune mission V14 n'est exploitable, le contrôleur V13 reste disponible pour les déblocages d'arbres/trous, relocalisations, deadlocks et défenses existantes. Toutes les actions sont ensuite exécutées par le même `Simulator` et les mêmes `Rules`.
