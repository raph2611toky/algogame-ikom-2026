# Vérification v0.11.0 / portfolio_v10

## Invariants

- `portfolio_v8` et `portfolio_v9` restent disponibles et leurs fichiers ne sont
  pas réécrits par v10.
- `portfolio_v10` est la stratégie recommandée et par défaut.
- La logique directe / relais / pierres / score peak reste héritée de v9/v8.
- Les ajouts v10 sont concentrés sur les coffres bloqués et la sécurité des machines.

## Tests spécifiques

`tests/test_strategy_v10.py` vérifie :

1. la détection du corridor commun de la carte 15×20 ;
2. la prédiction d'une poussée Excavator vers un bord non récupérable ;
3. la réservation de F pour intercepter une machine dangereuse ;
4. l'absence d'override de plusieurs méthodes centrales v8/v9.

## Vérifications fonctionnelles locales

Carte officielle :

- score 382 ;
- 5 pierres ;
- 1 coffre ;
- 0 perdu ;
- `OBJECTIVES_FINISHED`.

Carte de régression 15×20 : le diagnostic brut a dépassé le résultat v9
1 coffre / 3 pierres et a atteint au moins 3 coffres / 7 pierres sans perte avant
la poursuite du dernier objectif. Le calcul complet reste volontairement compatible
avec les `simulation-jobs`, car cette carte est nettement plus grande que la taille
d'évaluation annoncée.

## Suite pytest

La suite est exécutée par groupes pour éviter qu'un groupe de benchmarks lourds
ne monopolise le timeout global. Vérification finale : **97 tests réussis** (55 + 20 + 22).
