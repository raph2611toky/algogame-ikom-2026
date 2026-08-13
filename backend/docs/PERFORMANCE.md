# Performance de simulation

## Symptôme corrigé

La stratégie adaptative recalculait à chaque tick la valeur de nombreux obstacles. Cette estimation relançait des recherches de chemins et des planners de coffre sur plusieurs états hypothétiques. Sur certaines cartes 10x14, ce coût se répétait alors que des objectifs directs restaient déjà accessibles. `portfolio_v3` pouvait ensuite lancer deux passes adaptatives supplémentaires, dont une avec un seuil de blocage élevé, ce qui amplifiait fortement le temps total.

## Changements

- Les candidats de déblocage machine ne sont calculés que lorsqu'aucun plan de coffre direct n'est disponible ou lorsqu'aucun autre plan direct n'existe.
- La passe portfolio longue avec `stuck_bonus=12` a été supprimée.
- Une passe élargie n'est relancée que dans un cas réellement justifié par l'état final.
- Les très grandes cartes utilisent automatiquement `ScalableStrategy` avec des plans mis en cache et des budgets de recherche bornés.
- Le planner de coffre réduit son nombre maximal d'expansions sur les cartes dépassant 1000 puis 2500 cellules.
- `scalable_v1` est disponible explicitement dans Swagger.
- `scalable_max_ticks` permet de choisir la limite de ticks du profil stress. Valeur par défaut: 250.

## Détection automatique du profil stress

`portfolio_v3` bascule vers le profil scalable si au moins une condition est vraie:

- plus de 2500 cellules;
- plus de 12 machines;
- plus de 64 pierres;
- plus de 96 couples coffre/cachette potentiels.

Cette logique ne modifie donc pas le comportement normal attendu sur les cartes de taille compétition autour de 10x14.

## Cartes de régression

- `maps/regression/problematic_10x14.txt`: carte qui provoquait le ralentissement décrit.
- `maps/stress/complex_map_90x120.txt`: carte de stress volontairement très supérieure aux dimensions d'évaluation annoncées.
