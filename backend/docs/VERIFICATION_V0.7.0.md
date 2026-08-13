# Vérification v0.7.0

Cas de régression principal : carte 10x14 avec deux coffres et six pierres.

- portfolio_v5 : 1 coffre sécurisé, 6 pierres, arrêt prématuré `STRATEGY_END_GAME`.
- portfolio_v6 : 2 coffres sécurisés, 6 pierres, 0 coffre perdu, `OBJECTIVES_FINISHED`.
- Un événement `STONES_STOLEN` confirme la récupération de pierres transportées par une machine.
- La carte officielle conserve un résultat fort et termine correctement.
- Swagger multipart conserve `type: file` pour les paramètres fichier.
