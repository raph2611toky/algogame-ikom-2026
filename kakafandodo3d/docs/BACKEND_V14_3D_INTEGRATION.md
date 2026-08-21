# Intégration Backend V14 ↔ Kakafandodo 3D

## Source de vérité

Le gameplay de compétition est calculé par FastAPI V14. Le frontend 3D sert à importer, visualiser, lancer le calcul, rejouer les ticks, afficher le score et exporter `actions.txt`.

## Contrat d'élévation

Le backend renvoie `map.elevation_rows` et `map.has_elevation`. `StateSnapshotAdapter` et `BackendStateAdapter` convertissent ces données vers :

- `height_map`
- `has_explicit_elevation`
- `max_elevation`

Le plateau 3D continue donc d'utiliser son modèle historique sans dupliquer les règles d'élévation.

## Compatibilité anciennes maps 3D

`MissionSelect` détecte une éventuelle section `ELEVATION` inline, conserve uniquement les H lignes ASCII pour `map_text`, compacte les H lignes de hauteurs et les transmet comme `elevation_text` au backend V14.

Les fichiers séparés restent prioritaires lorsqu'un `elevation.txt` explicite est choisi.

## Simulation asynchrone

Pour les cartes complexes, `MissionLaunch` utilise :

- `POST /simulation-jobs`
- `GET /simulation-jobs/{job_id}`
- `GET /simulation-jobs/{job_id}/result`

Cela évite de bloquer sur un gros calcul V14.

## Replay 3D

`GameScreen` applique chaque snapshot FastAPI via `StateSnapshotAdapter`, puis transmet le `GameState` au `GameBoard`/`Plan3DGenerator`.

Le HUD affiche également le niveau `Z` courant de F et M.

## Régression

Le calcul local historique est conservé uniquement pour certains anciens self-tests et outils de développement. Le chemin normal MissionSelect → MissionLaunch → GameScreen utilise FastAPI V14.
