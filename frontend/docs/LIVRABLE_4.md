# Livrable 4 — Presentation & Visual Polish

Cette étape ajoute la couche présentation au moteur du Livrable 3 sans modifier les règles de simulation.

## Ajouts

- animations enrichies des héros, machines et coffres ;
- effets particules pour hack, excavation, coupe, remplissage, collecte, coffre caché/perdu ;
- réactions visuelles (pulses, flashs, badges, secousses) ;
- sons courts dans `assets/audio/liv4/` ;
- caméra de présentation basée sur un zoom/pan léger du panneau de jeu ;
- écran `MissionLaunch.tscn` avec briefing et compte à rebours 3-2-1-GO ;
- HUD réactif : score et objectifs pulsent quand ils changent ;
- bannière événementielle pour les actions importantes ;
- le réglage `EFFETS` agit également sur la quantité de particules.

## Fichiers principaux

- `scripts/audio/game_audio.gd`
- `scripts/game/effect_pulse.gd`
- `scripts/game/entity_view.gd`
- `scripts/game/game_board.gd`
- `scripts/game/game_screen.gd`
- `scripts/menu/mission_launch.gd`
- `scenes/menu/MissionLaunch.tscn`

## Important — assets audio

Les sons du Livrable 4 sont des sons de prototype générés procéduralement pour tester l'intégration technique. Pour une soumission artistique exigeant des assets réalisés manuellement par l'équipe, remplacez-les par vos propres enregistrements/créations et conservez les preuves du processus de production.

## Test recommandé

1. Ouvrir `project.godot`.
2. Laisser Godot importer les WAV/SVG/PNG.
3. Lancer `F5`.
4. `COMMENCER` → `JOUER` → sélectionner/importer une map.
5. Cliquer `LANCER LA SIMULATION`.
6. Vérifier l'écran de briefing puis le compte à rebours.
7. Observer les effets `HACK`, `CUT`, `DIG`, collecte et coffres.
8. Tester `x1`, `x2`, `x4`, pause et paramètres rapides.
