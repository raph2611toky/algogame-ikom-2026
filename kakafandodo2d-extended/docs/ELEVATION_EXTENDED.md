# Kakafandodo 2D Extended — elevation.txt + Backend V14

Cette variante garde le gameplay 2D et ajoute un rendu **2D-extended / 2.5D léger** pour le relief du GDD Addendum.

## Contrat de fichiers

- `map.txt` conserve le format officiel : `H W TIME_LIMIT` puis `H` lignes ASCII.
- `elevation.txt` contient exactement `H` lignes de `W` chiffres.
- cellule accessible : niveau `1..9`.
- rocher `#` : valeur `0` obligatoire.
- sans `elevation.txt`, le frontend/backend restent en mode historique plat (`0`).

Le frontend envoie le contenu des deux fichiers au backend FastAPI V14 dans `mission.map_text` et `mission.elevation_text`.

## Rendu en couches

Pour une cellule de niveau `N` :

```text
surface de la case
==================
  croûte niveau 1
  croûte niveau 2
  ...
  croûte niveau N
```

Le nombre de bandes visibles est donc exactement `N`.

- niveau `1` -> 1 croûte ;
- niveau `5` -> 5 croûtes ;
- niveau `9` -> 9 croûtes ;
- rocher `0` -> aucune croûte d'altitude (0 est un marqueur de rocher, pas une altitude de gameplay).

La surface, les props, les coffres, les machines et les héros sont tous dessinés sur le sommet de leur cellule. Les déplacements backend restent la source de vérité : le rendu ne modifie aucune règle.

## Import utilisateur

`MissionSelect` :

1. importer `map.txt` ;
2. le frontend recherche automatiquement, dans le même dossier :
   - `<nom_map>_elevation.txt` ;
   - `<nom_map>.elevation.txt` ;
   - `elevation.txt` ;
3. si nécessaire, utiliser **CHOISIR ELEVATION.TXT** pour sélectionner le fichier manuellement ;
4. le backend valide la cohérence map/elevation avant d'activer le bouton de simulation.

## Synchronisation backend

Les routes utilisées sont compatibles V14 :

- `POST /api/v1/maps/parse` avec `elevation_text` ;
- `POST /api/v1/simulation-jobs` avec `mission.elevation_text` ;
- `POST /api/v1/simulations/replay-text` avec `mission.elevation_text`.

La réponse backend fournit `map.elevation_rows` et `map.has_elevation`. Le frontend reconstruit cette matrice dans `GameState.elevations`, puis la conserve pendant tout le replay des ticks.

## Fichiers de démonstration

- `data/maps/example_map.txt`
- `data/maps/example_map_elevation.txt`
- `data/maps/tests/v14_complex_15x20.txt`
- `data/maps/tests/v14_complex_15x20_elevation.txt`

La carte 15x20 est recommandée pour vérifier visuellement les niveaux 1 à 9 et la synchronisation avec `portfolio_v14`.
