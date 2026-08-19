# Portfolio v12 — ScoreMax adaptatif

## Objectif

`portfolio_v12` vise d'abord le **score final réellement obtenu par le moteur**, pas la fidélité à une seule heuristique.
Il garde le coeur comportemental V11 → V10 → V9 → V8 et l'addendum elevation/look-ahead déjà intégré, puis ajoute un superviseur de portefeuille borné.

## Pourquoi un superviseur et non un vote action par action ?

Les versions précédentes montrent que des heuristiques différentes gagnent sur des familles de cartes différentes :

- le coeur V11/V10 est fort sur les dépendances, handoff stamina, déblocages X/G, protection de coffres et parallélisme ;
- `heuristic_v1` peut être meilleur sur les routes directes, les arbres-portails et les cas où il faut laisser une machine autonome travailler avant de l'intercepter ;
- `portfolio_v4` reste très compétitif sur la délégation aux machines et certains cas chest-first ;
- `portfolio_v10` protège contre les régressions de parallélisme de V11 sur certains corridors/risques machines.

Mélanger les premières actions de ces stratégies créerait des oscillations et casserait leurs plans internes. V12 exécute donc chaque candidat **indépendamment dans le même Simulator**, applique `trim_to_best_score_prefix`, puis conserve le résultat classé maximal par : score, coffres, pierres, coffres perdus, temps restant, ressources restantes, longueur de trajectoire.

## Ensemble non redondant

Sur la zone petite (<≈240 cellules), V12 compare :

1. `v12_core` (V11/V10/V9/V8 + addendum),
2. `heuristic_v1`,
3. `portfolio_v4`,
4. `portfolio_v10`.

L'analyse des benchmarks précédents montre que cet ensemble de quatre comportements couvre les gagnants observés sans exécuter toutes les versions historiques. Les versions V5/V6/V7/V8/V9 restent disponibles pour benchmark mais n'ajoutaient pas de victoire unique sur la suite observée une fois ces quatre familles présentes.

## Adaptation à la complexité

Le superviseur évite volontairement de lancer quatre planificateurs lourds partout :

- <= 240 cellules, charge objectifs raisonnable : ensemble complet ;
- 241–320 cellules sans chaîne trou/arbre : coeur + heuristic + V4 ;
- carte moyenne avec au plus un obstacle structurel : coeur + heuristic ;
- double dépendance X+G / cartes plus complexes : coeur V12 seul ;
- >= 700 cellules, >= 9 machines, >= 48 pierres ou charge coffre×cachette >= 40 : `scalable_v1` borné.

Cela corrige le problème pratique observé où une carte 30×40 (1200 cellules) pouvait dépasser 600 s : V12 bascule avant la falaise historique de complexité.

## Propriété de dominance

Lorsque l'ensemble `{v12_core, heuristic, v4, v10}` est activé et que les candidats terminent, le résultat V12 est **au moins aussi bon en score** que chacun de ces candidats sur le même moteur, puisqu'il choisit le meilleur résultat après simulation complète.

Ce n'est pas une preuve d'optimalité globale du jeu (le problème de planification reste combinatoire), mais c'est une garantie de non-régression par rapport aux candidats effectivement évalués.

## Résultats de contrôle après intégration

Sur plusieurs cas complexes déjà utilisés pour le benchmark, avec le backend actuel :

- `23_fill_hole_gate_for_chest` : 233 → **362** ;
- `24_cut_tree_gate_for_chest` : 256 → **403** ;
- `26_let_grappler_auto_secure_chest` : 390 → **395** ;
- `27_machine_harvest_then_intercept` : 383 → **384** ;
- `28_two_autonomous_machine_chest_lanes` : 529 → **530** ;
- `29_stop_one_machine_let_other_score` : **526** ;
- `33_machine_buffer_corridor_treasure` : 371 → **373** ;
- `34_do_not_hack_before_grappler_work` : 407 → **408** ;
- `36_two_machine_stone_harvest_and_steal` : 541 → **544**.

Le cas `32_parallel_dual_machine_unlock` reste sur le coeur V12 seul afin d'éviter les probes historiques coûteux : **590**, objectifs terminés, environ 12.5 s lors du contrôle local.

Le stress `20_large_sparse_30x40` est désormais reconnu par la politique V12 comme stress et passe au profil borné au lieu d'entrer dans le portefeuille exhaustif ; un contrôle local a produit un résultat en ~36.6 s au lieu du timeout de 600 s observé dans l'ancien benchmark.
