# KAKAFANDODO v0.4.2 - correction performance

- `backend/` : backend corrigé.
- `frontend_patch/kakafandodo2d/scripts/api/backend_api.gd` : timeout spécifique de simulation à 120 s et message correct pour HTTPRequest.RESULT_TIMEOUT.
- `frontend_patch/kakafandodo2d/scripts/core/game_session.gd` : valeur par défaut `scalable_max_ticks=250`.

Pour appliquer le patch frontend, recopier uniquement ces deux fichiers aux mêmes chemins dans votre projet Godot existant.
