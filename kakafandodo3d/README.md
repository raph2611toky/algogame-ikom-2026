# Kakafandodo 3D Extended — Backend V14 + elevation

Cette version conserve le plateau 3D avancé de `kakafandodo3d` et remplace l'ancien calcul local par l'intégration directe du backend FastAPI V14.

## Flux réel

1. Godot importe `map.txt`.
2. Il détecte automatiquement `elevation.txt`, `<map>_elevation.txt` ou `<map>.elevation.txt`.
3. Les anciennes maps 3D contenant une section `ELEVATION` inline restent acceptées : le frontend sépare automatiquement cette section avant l'envoi au backend V14.
4. `/api/v1/maps/parse` valide la carte et le relief.
5. `/api/v1/simulation-jobs` calcule la stratégie `portfolio_v14` sans bloquer l'interface HTTP.
6. Godot récupère la simulation complète et rejoue les snapshots/ticks du backend sur le plateau 3D.
7. `actions.txt` provient directement du résultat FastAPI et peut être exporté depuis l'écran de résultats.

Le frontend ne recalcule donc plus les décisions des héros pendant une mission normale : le backend V14 est la source de vérité pour les règles, l'élévation, les machines, le score et les actions.

## Lancer

### Windows

`START_BACKEND.bat`, puis ouvrir `project.godot` et lancer F5.

### Linux/macOS

```bash
./start_backend.sh
```

Puis lancer le projet Godot.

Backend par défaut : `http://127.0.0.1:8000/api/v1`.

## Formats elevation

Le format officiel recommandé est séparé :

- `map.txt` : `H W TIME_LIMIT` + H lignes ASCII ;
- `elevation.txt` : H lignes de W chiffres ;
- niveaux accessibles : `1..9` ;
- rochers `#` : `0`.

Pour compatibilité avec l'ancien projet 3D, le frontend accepte également :

```text
H W TIME_LIMIT
<grille>
ELEVATION
<hauteurs>
```

Cette représentation est convertie côté Godot en deux payloads distincts avant validation FastAPI.

## Rendu 3D

Le renderer 3D existant est conservé : terrasses, pentes, couches, caméra orbitale, props et entités dynamiques. Les `elevation_rows` renvoyés par FastAPI sont convertis en `GameState.height_map`, puis envoyés au `Plan3DGenerator`.

Les changements de terrain pendant le replay (DIG, FILL, CUT) et les déplacements F/M/X/G utilisent les snapshots exacts du backend.

## Maps de test

- `data/maps/demo_simulation/map.txt` + `elevation.txt`
- `data/maps/tests/backend_v14/v14_complex_15x20.txt`
- `data/maps/tests/backend_v14/v14_complex_15x20_elevation.txt`
- `data/maps/tests/backend_v14/complex_climb_15x20.txt`
- `data/maps/tests/backend_v14/complex_climb_15x20_elevation.txt`

## Backend embarqué

Le dossier `backend/` contient la version V14 actuelle (`portfolio_v14`). Il possède un `.gdignore` afin que Godot n'importe pas les fichiers Python.
