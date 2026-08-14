# portfolio_v7 — cache structurel et orchestration collaborative

`portfolio_v7` conserve les règles et les priorités métier de `portfolio_v6` : coffres directement sécurisables en priorité, déblocage par Excavator/Grappler lorsque nécessaire, collaboration F/M, collecte des pierres libres et récupération des pierres transportées par les machines.

## Problème corrigé

Sur les cartes plus grandes, la stratégie précédente recalculait trop souvent les mêmes analyses structurelles : possibilité géométrique d'un coffre, ensemble de trous/arbres à supprimer, puis plusieurs recherches Sokoban. Ces calculs étaient déclenchés à nouveau lorsque les héros ou les machines se déplaçaient, alors que la structure utile de la carte n'avait pas réellement changé.

`portfolio_v7` met en cache les profils de déblocage avec une signature basée sur les coffres, trous, arbres, rochers et cachettes. Un déplacement ordinaire de F/M ou d'une machine ne détruit donc plus ce cache.

Le planner direct des coffres utilise aussi un budget d'expansion adapté au nombre de cellules afin de conserver une recherche précise sur les petites cartes sans laisser une seule recherche consommer un temps disproportionné sur une carte moyenne.

## Fin de stratégie

La stratégie distingue un objectif momentanément difficile d'un coffre structurellement impossible. Un coffre n'est exclu que si aucun plan vers une cachette n'existe même après suppression hypothétique des obstacles modifiables pertinents.

Lorsque toutes les pierres libres et transportées ont été récupérées et que les coffres restants sont réellement structurellement impossibles, la stratégie arrête le calcul avec `NO_REACHABLE_OBJECTIVES` au lieu de générer des centaines de `WAIT` jusqu'au `TIME_LIMIT`.

## Pierres transportées par les machines

Les choix de pierres comprennent les pierres encore sur la carte et les machines dont `carried_stones > 0`. Une cible machine est valorisée par le nombre de pierres transportées et par le coût pour F/M de rejoindre sa case. Le moteur transfère ensuite toutes les pierres de la machine au héros lorsqu'ils partagent la même cellule.

## Cartes complexes

`portfolio_v7` reste une stratégie de recherche, pas une garantie d'optimum mathématique global. Pour ne pas bloquer l'interface pendant le calcul, le frontend 2D utilise les routes `/api/v1/simulation-jobs*` : le calcul se fait côté backend et Godot interroge son état sans garder une requête HTTP longue ouverte.
