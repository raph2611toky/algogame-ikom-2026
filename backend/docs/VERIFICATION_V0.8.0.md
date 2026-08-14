# Vérification v0.8.0

## Stratégie

- `portfolio_v7` est la stratégie par défaut.
- Le catalogue dynamique est exposé par `GET /api/v1/strategies`.
- Les anciennes stratégies restent disponibles pour comparaison.
- La carte officielle conserve le score local 380 avec tous les objectifs terminés.
- La régression 10x14 de `portfolio_v6` conserve 2 coffres, 6 pierres et `OBJECTIVES_FINISHED`.

## Carte 15x20 / TIME_LIMIT 700

La carte `maps/regression/user_15x20_700.txt` contient quatre coffres. Le profil structurel classe le coffre initial `(13,0)` comme impossible : situé sur la colonne 0, il ne peut pas recevoir une poussée vers la droite, et le mur inférieur/intermédiaire ne permet pas une route verticale vers la cachette. Les trois autres coffres sont classés structurellement possibles.

Avec `portfolio_v7`, la simulation de référence sécurise 3 coffres, collecte les 9 pierres et s'arrête après 244 ticks avec `NO_REACHABLE_OBJECTIVES` au lieu d'attendre 700 ticks. Le calcul observé dans l'environnement de vérification est d'environ 32 secondes ; cette mesure est indicative et dépend du processeur.

## HTTP / Swagger

- Les routes multipart de `/swagger.json` utilisent `formData` et `type: file`.
- `/simulation-jobs/upload` répond avec HTTP 202 et un petit statut de job.
- `/openapi.json` reste l'OpenAPI canonique FastAPI.
- GZip est activé pour les réponses importantes.

## Godot 2D

- Hôte et port backend sont modifiables localement dans Paramètres.
- La liste des stratégies vient de `/api/v1/strategies`.
- La stratégie choisie est sauvegardée dans les paramètres et envoyée au backend.
- Le lancement de mission passe par un job asynchrone et affiche le temps de calcul pendant le polling.
