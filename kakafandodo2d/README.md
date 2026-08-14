# Kakafandodo — AlgoGames 2 / Godot 4

Projet Godot 4 complet pour la couche interface, l'import de cartes ASCII, la simulation 2D dynamique et l'export `actions.txt`.

## Version actuelle

Cette code correspond aux finition UI/UX, menu principal proche de la maquette, écran paramètres conformisé, intégration du flux mission → simulation → résultats, et packaging de la version compétition.

## Démarrage

1. Ouvrir `project.godot` dans **Godot 4.x**.
2. Laisser Godot importer les textures et les sons.
3. Lancer avec **F5**.
4. `COMMENCER` → menu principal.
5. `JOUER` ou `MISSIONS` → écran d'import / sélection de carte.
6. Choisir un `map.txt`, vérifier l'aperçu, puis lancer la mission.
7. La simulation est entièrement automatique : aucun contrôle humain ne commande F/M pendant la partie.
8. À la fin, `actions.txt` est exporté et le score est affiché.

## Parcours UI

```text
StartScreen
  -> MainMenu
      -> MissionSelect
          -> MissionLaunch
              -> GameScreen
                  -> ResultScreen
      -> SettingsScreen
      -> CreditsScreen
```

## Format `map.txt`

Exemple officiel inclus dans `data/maps/example_map.txt` :

```text
5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
```

Voir `docs/GDD_IMPLEMENTATION_MATRIX.md` pour la correspondance complète entre règles et code.

## Architecture rapide

```text
scripts/game/map_loader.gd        parser/validation map.txt
scripts/game/game_state.gd        état déterministe de la partie
scripts/game/simulation_engine.gd règles et résolution par tick
scripts/game/game_board.gd        rendu dynamique de la grille
scripts/game/entity_view.gd       rendu des personnages et machines
scripts/ai/demo_brain.gd          baseline d'actions remplaçable
scripts/io/actions_writer.gd      export actions.txt
scripts/core/game_session.gd      carte courante + paramètres persistants
scripts/menu/*.gd                 flux UI complet
```

## Tests manuels fournis

- `data/maps/tests/hop_climb.txt`
- `data/maps/tests/machines_and_chest.txt`
- `data/maps/tests/multi_machine_sync.txt`
- `data/maps/tests/livrable3_visual_showcase.txt`

## Important — algorithme compétitif

`DemoBrain` est seulement un solveur de démonstration permettant de faire tourner tout le pipeline. Le score final sur hidden maps dépendra de votre vrai solveur. Remplacez-le en conservant l'interface `get_actions(state) -> {"F": ..., "M": ...}`.

## Important — Artistic Prize

interface provisoire en 2D

## Backend FastAPI dynamique

Cette version 2D utilise par défaut `http://127.0.0.1:8000/api/v1`, mais l’hôte et le port sont modifiables dans **Paramètres** et sauvegardés localement.

1. `MissionSelect` envoie le `map.txt` à `POST /maps/upload`.
2. Les paramètres chargent `GET /strategies` pour construire dynamiquement le choix de stratégie.
3. `MissionLaunch` crée un job avec `POST /simulation-jobs`, puis interroge `GET /simulation-jobs/{job_id}`.
4. Une fois le job terminé, Godot récupère `GET /simulation-jobs/{job_id}/result`.
5. `GameScreen` joue `initial_state` puis `ticks[]` sans recalculer les règles.
6. `actions_txt` est enregistré dans `user://actions.txt`.
7. Les paramètres applicatifs utilisent `/settings` avec `user://settings.cfg` comme fallback local ; l’IP et le port du backend restent volontairement locaux au frontend.

Test Godot : `res://scenes/tests/BackendIntegrationTest.tscn`.
