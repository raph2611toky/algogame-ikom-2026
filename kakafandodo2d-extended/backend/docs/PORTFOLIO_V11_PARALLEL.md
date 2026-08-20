# Portfolio v11 — parallélisme progressif par rôles

`portfolio_v11` est une couche **au-dessus de portfolio_v10**. Le cœur v10/v9/v8
reste la référence pour les routes de coffres, le handoff stamina, les opportunités
partagées, les micro-plans machines, l'anti-oscillation/deadlock et la protection
des coffres contre les machines autonomes.

## Problème corrigé

L'ancien essai v11 pouvait remplacer trop agressivement une décision v10 par
`WAIT` ou par une règle stricte sur les pierres. Il empêchait donc parfois le
second héros de travailler alors qu'un autre coffre avait déjà une tâche utile.

Le nouveau v11 ne remplace plus le plan principal. Il ne s'active que lorsqu'une
**indépendance concrète** est prouvée :

1. un héros possède déjà une route vers un coffre direct ;
2. un autre coffre reste bloqué ;
3. le héros libre possède une `MachineTask` v10 exécutable immédiatement sur ce
   second coffre ;
4. ce héros n'est pas réservé par v8/v9 pour un relais stamina du coffre actif.

Dans ce cas seulement, le héros libre prépare le second coffre en parallèle.

## Ordre des tâches secondaires

Pendant un coffre direct long :

1. protections X/G de v10 ;
2. route directe du propriétaire ;
3. relais stamina v8/v9 si nécessaire ;
4. tâche machine réelle sur un autre coffre ;
5. comportement v10 d'origine (pierres, WAIT, etc.).

Le nouveau v11 **ne lance jamais de staging machine lointain** comme simple
optimisation secondaire. Un staging reste la responsabilité du plan principal
v10, car éloigner un futur relayeur sur une hypothèse est précisément ce qui
avait provoqué des régressions.

## Régression 15x20 utilisateur

Sur `maps/regression/user_15x20_shared_opportunity.txt`, les 350 premiers ticks de
v11 ont été comparés action par action au v10 validé : aucune divergence.

État au tick 350 :

- coffres sécurisés : 3/4 ;
- pierres : 7/9 ;
- stamina totale : 0 ;
- batterie totale : 89 ;
- temps restant : 350 ;
- score correspondant : 822.

Cela garantit que la correction v11 ne reproduit pas la régression de l'ancien
v11 sur cette carte.

## Test de parallélisme indépendant

`tests/test_strategy_v11.py` contient une carte de 9x20 où :

- F pousse un coffre libre vers sa cachette ;
- M peut soit partir vers une pierre lointaine, soit hacker G pour couper l'arbre
  qui bloque un second coffre.

v10 choisit la pierre secondaire ; v11 garde F sur le coffre et fait hacker G à M.
Au tick suivant, F continue à pousser pendant que M lance le contrôle de G.
