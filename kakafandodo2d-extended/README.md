# Kakafandodo 2D Extended — Godot 4 + FastAPI V14

Version étendue du frontend Kakafandodo pour **AlgoGames 2**, synchronisée avec le backend V14 et le nouveau fichier officiel `elevation.txt`.

## Ce qui change

- import conjoint `map.txt` + `elevation.txt` ;
- auto-détection du fichier d'élévation dans le dossier de la map ;
- validation des deux fichiers par le backend avant la mission ;
- `elevation_rows` conservé dans le `GameState` frontend pendant tout le replay ;
- rendu 2D-extended : **une croûte × niveau d'élévation** pour chaque cellule ;
- objets, coffres, héros et machines suivent visuellement le sommet de la cellule ;
- niveau affiché discrètement sur la case lorsque la taille le permet ;
- HUD F/M affiche aussi `Z<niveau>` ;
- stratégie frontend par défaut alignée sur `portfolio_v14` ;
- aucune règle de compétition n'est recalculée par le rendu : FastAPI V14 reste la source de vérité.

## Démarrage complet

### 1. Backend

Depuis le dossier `backend/` inclus dans cette archive :

```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows : .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend Godot

1. ouvrir `project.godot` avec **Godot 4.7** ;
2. lancer avec **F5** ;
3. `COMMENCER` → `JOUER` ;
4. importer `map.txt` ;
5. laisser le jeu détecter `elevation.txt` ou cliquer sur **CHOISIR ELEVATION.TXT** ;
6. vérifier l'aperçu en couches ;
7. lancer la simulation.

## Format

`map.txt` :

```text
5 7 100
G+.M..+
.###tt#
.o*.+.@
o##t#tX
.F#++..
```

`elevation.txt` correspondant :

```text
1111111
1000110
1111111
1001011
1101111
```

Règles de parsing :

- terrain accessible : `1..9` ;
- rocher `#` : `0` ;
- même hauteur et même largeur que la grille de `map.txt` ;
- absence d'`elevation.txt` = mode plat historique, conservé pour compatibilité.

## Rendu des cellules

Une cellule d'élévation 4 est dessinée comme :

```text
┌──────────────┐  surface
└──────────────┘
████████████████  couche 1
████████████████  couche 2
████████████████  couche 3
████████████████  couche 4
```

Le rendu est volontairement simple : il ajoute seulement l'épaisseur/croûte demandée sans transformer le gameplay 2D en vraie 3D.

Voir `docs/ELEVATION_EXTENDED.md` pour les détails techniques.

## Flux backend

```text
MissionSelect
  map.txt + elevation.txt
        ↓
POST /maps/parse
        ↓
MissionLaunch
        ↓
POST /simulation-jobs
        ↓
portfolio_v14
        ↓
GET /simulation-jobs/{id}/result
        ↓
GameScreen
  replay initial_state + ticks[]
  avec la même matrice d'élévation
        ↓
actions.txt / ResultScreen
```

Le frontend n'essaie donc pas de deviner les mouvements autorisés selon le relief : il affiche exactement les états produits par le backend V14.

## Cartes de test

- `data/maps/example_map.txt` + `example_map_elevation.txt`
- `data/maps/tests/v14_complex_15x20.txt` + `v14_complex_15x20_elevation.txt`

La seconde est la carte complexe 15×20 utilisée pour tester les niveaux 1–9 et l'IA globale V14.
