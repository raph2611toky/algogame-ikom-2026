# Vérification v0.10.0 / portfolio_v9

Objectif de cette version : conserver la qualité de `portfolio_v8` et corriger uniquement la coordination des PUSH longs.

Vérifications automatisées ajoutées :

1. `portfolio_v9` est la stratégie par défaut et la carte officielle de référence reste >= 380 points localement.
2. Le mouvement normal du coffre suivi n'invalide plus sa route cachée, mais un vrai changement de terrain l'invalide.
3. Sur un long coffre unique, v9 fait un relais par segment au lieu d'un ping-pong après chaque PUSH.
4. Le helper se déplace vers un point de relais pendant que le pousseur actif continue.
5. Avec deux coffres directs distincts, les deux héros conservent les PUSH parallèles.
6. Lorsque F et M commencent avec peu de stamina, un même coffre n'a jamais deux pousseurs au même tick et le nombre de changements de propriétaire reste borné.
7. Une pression de travail spécialisé sur un autre coffre peut déclencher un relais plus tôt sans lancer le planner lourd à chaque tick.
8. `portfolio_v8` reste disponible dans `/api/v1/strategies` pour benchmark comparatif.

Le frontend 2D conserve également la configuration runtime IP/port du backend et récupère dynamiquement le catalogue des stratégies.

## Résultats locaux de non-régression

Carte officielle `5x7` : `portfolio_v9` = score 382, 49 ticks, 5 pierres, 1 coffre, 0 perdu, `OBJECTIVES_FINISHED`.

Régression utilisateur `10x14` :

- `portfolio_v8` = score 633, 64 ticks, 6 pierres, 2 coffres, stamina totale 77, batterie totale 185.
- `portfolio_v9` = score 633, 64 ticks, 6 pierres, 2 coffres, stamina totale 77, batterie totale 185.

Le nouveau relais n'altère donc pas cette carte où v8 était déjà très bon.

Régression longue `1x30` :

- v8 = score 338, 55 ticks, 8 changements de pousseur dans la séquence de PUSH.
- v9 = score 352, 26 ticks, 1 seul changement de pousseur : F effectue le premier segment, M termine le second.

Les scores ci-dessus sont ceux du moteur local et servent à la comparaison de versions; l'évaluateur AlgoMada reste la référence officielle.
