# Vérification — portfolio_v12 ScoreMax

## Tests de code

Commandes exécutées après l'intégration :

```text
python -m compileall -q app
PASS

pytest -q tests/test_strategy_v12.py tests/test_strategy_v11.py tests/test_strategy_v10.py tests/test_strategies_api.py tests/test_settings.py
15 passed

pytest -q tests/test_strategy_v8.py tests/test_strategy_v9.py tests/test_strategy_v10.py tests/test_strategy_v11.py tests/test_strategy_v12.py tests/test_strategies_api.py tests/test_settings.py tests/test_simulation_jobs.py
32 passed
```

Une exécution de `pytest -q` complet a ensuite été lancée ; elle n'a affiché aucune erreur sur les ~70 premiers tests mais a dépassé la fenêtre d'exécution disponible avant la fin de la suite exhaustive. Cette note n'affirme donc pas que les 161 tests complets ont terminé.

## Contrôles stratégiques

Les contrôles de score sont enregistrés dans `docs/V12_SCOREMAX_VALIDATION.csv`.

Points notables sur le backend/règles actuels :

- cas 23 : 362, coffre + 2 pierres ;
- cas 24 : 403, le probe heuristique récupère le coffre derrière l'arbre ;
- cas 26 : 395, meilleure exploitation du Grappler autonome ;
- cas 28 : 530, V4 améliore d'un point la délégation des deux machines ;
- cas 29 : 526, le coeur V12 dépasse déjà l'ancien meilleur benchmark ;
- cas 33 : 373 ;
- cas 34 : 408 ;
- cas 36 : 544 ;
- cas 32 : politique volontairement `v12_core` seule, 590 en ~12.5 s ;
- stress 30x40 : la politique sélectionne `scalable` avant la falaise des anciens portfolios ; un résultat a été observé vers 36.6 s au lieu du timeout historique de 600 s.

## Limite importante

V12 maximise le score **parmi les trajectoires candidates qu'il décide d'évaluer**. Cela donne une garantie de dominance locale de portefeuille, pas une preuve mathématique d'optimalité globale sur l'espace de toutes les séquences d'actions possibles.
