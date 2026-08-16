# KAKAFANDODO Backend — FastAPI + moteur de règles + IA

Backend local pour KAKAFANDODO / AlgoGames 2. Il est conçu pour que Godot reste responsable du rendu, tandis que FastAPI calcule la carte logique, les règles, les actions, les ressources, le score et le replay.

## Démarrage

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interfaces de documentation :

```text
Swagger complet : http://127.0.0.1:8000/docs
Swagger JSON     : http://127.0.0.1:8000/swagger.json
OpenAPI FastAPI  : http://127.0.0.1:8000/openapi.json
ReDoc            : http://127.0.0.1:8000/redoc
```

### Pourquoi `/swagger.json` est en Swagger 2.0

FastAPI garde son schéma OpenAPI 3.1 canonique dans `/openapi.json`. Pour respecter le besoin UI du projet, `/docs` consomme une vue documentaire Swagger 2.0 générée **à partir du vrai schéma FastAPI** : les routes multipart n'y ont aucun `requestBody`; chaque fichier/champ est affiché comme paramètre manuel `formData`.

Exemples :

- `/api/v1/maps/upload` → `file` ;
- `/api/v1/simulations/upload` → `file`, `name`, `strategy_json` ;
- `/api/v1/simulation-jobs/upload` → `file`, `name`, `strategy_json` ;
- `/api/v1/simulations/replay-upload` → `map_file`, `actions_file`, `name`, `stop_when_objectives_finished`.

Les modèles de réponse du Swagger sont les mêmes modèles Pydantic que ceux utilisés par les vues FastAPI.


## Clarification machines — buffer AlgoMada

Le moteur suit la clarification la plus récente du game runner : une machine conserve une case vide de marge devant elle lorsqu'une autre machine se trouve dans sa direction. `...G.X..` interdit donc le MOVE de `G`, même si `X` est orienté dans le même sens ou va lui-même bouger. Les convois ne sont plus autorisés.

Le motif coffre/machine utilise une marge plus large : dans `..G.*X`, avec les machines dirigées vers le coffre, les deux mouvements sont refusés. Les mêmes contrôles s'appliquent à `HACK_MOVE`; une machine hackée reste immobile sans rotation automatique et sans coût batterie si le déplacement violerait le buffer.

## Architecture

```text
backend/
├── app/
│   ├── api/
│   │   ├── router.py
│   │   ├── swagger.py
│   │   └── routes/
│   │       ├── contracts.py
│   │       ├── health.py
│   │       ├── maps.py
│   │       ├── settings.py
│   │       ├── strategies.py
│   │       ├── simulation_jobs.py
│   │       └── simulations.py
│   ├── core/
│   ├── domain/
│   │   ├── enums.py
│   │   ├── mappings.py
│   │   └── models.py
│   ├── engine/
│   │   ├── actions_parser.py
│   │   ├── actions_writer.py
│   │   ├── chest_planner.py
│   │   ├── machine_pathfinding.py
│   │   ├── machine_planner.py
│   │   ├── map_parser.py
│   │   ├── pathfinding.py
│   │   ├── score_pathfinding.py
│   │   ├── rules.py
│   │   ├── scoring.py
│   │   ├── simulator.py
│   │   ├── snapshot.py
│   │   ├── strategy.py
│   │   ├── strategy_v2.py
│   │   ├── strategy_v4.py
│   │   ├── strategy_v5.py
│   │   ├── strategy_v6.py
│   │   ├── strategy_v7.py
│   │   ├── strategy_registry.py
│   │   └── strategy_scalable.py
│   ├── schemas/
│   ├── services/
│   │   ├── settings_service.py
│   │   ├── simulation_job_service.py
│   │   └── simulation_service.py
│   └── main.py
├── docs/
├── maps/
├── output/
├── scripts/
├── tests/
├── requirements.txt
├── pyproject.toml
└── run.sh
```

## Format `map.txt`

```text
H W TIME_LIMIT
<row 1>
...
<row H>
```

Alphabet :

```text
. vide
F Ikotofosa
M Imahaki
# rocher
t arbre
o trou
X Excavator
G Grappler
* coffre
+ pierre
@ cachette
```

Le parser valide les dimensions, le temps, l'alphabet, la présence unique de F/M et les limites de sécurité.

## Moteur de règles

Le moteur implémente notamment :

- déplacements orthogonaux et WAIT ;
- Ikotofosa : saut d'un seul trou, contrôle des Excavators, `HACK_FILL` ;
- Imahaki : franchissement d'un seul arbre, contrôle des Grapplers ;
- stamina, batterie et récupération ;
- pierres, coffres, cachettes, trous, arbres et rochers ;
- poussées simultanées et pertes/sécurisation de coffres ;
- pierres ramassées par les machines puis récupérables par F/M ;
- `HACK`, `HACK_MOVE`, `HACK_CW`, `HACK_CCW`, `HACK_FILL` et compatibilité `HACK_CUT` ;
- MOVE machine en deux ticks ;
- routines autonomes X/G, orientations initiales et rotations lorsqu'ils sont bloqués ;
- hack : arrêt des mouvements/rotations automatiques et suspension du DIG de l'Excavator ;
- Grappler hacké : CUT automatique toujours actif lorsqu'il rencontre un arbre ;
- buffer d’une case vide devant une machine lorsqu’une autre machine se trouve dans sa direction ;
- buffer spécial coffre + machine sur deux cases, y compris pour `HACK_MOVE` ;
- protection anti-collision lors des poussées de coffres entre machines ou héros/machine ;
- Excavator : creusement après cinq déplacements automatiques ;
- Grappler : coupe automatique d'un arbre occupé ;
- collisions entre machines ;
- score, snapshots, replay et `actions.txt`.


## IA : `portfolio_v10` par défaut

`portfolio_v10` conserve le cœur `portfolio_v9` / `portfolio_v8` et ajoute une couche ciblée pour les coffres bloqués : détection d'obstacles communs à plusieurs coffres, micro-plans machines engagés, anti-oscillation/deadlock, protection globale des coffres contre une machine autonome et collecte parallèle du héros non requis.

Le catalogue dynamique reste disponible via `GET /api/v1/strategies`; les anciennes stratégies restent sélectionnables pour comparaison. Voir `docs/PORTFOLIO_V10.md` et `docs/VERIFICATION_V0.11.0.md`.

## IA historique : `portfolio_v9`

Le catalogue est dynamique via `GET /api/v1/strategies`. Le frontend 2D peut donc choisir une stratégie sans modification de code côté menu.

```text
portfolio_v9   historique, cœur v8 + relais minimal anti ping-pong
portfolio_v8   précédent, stamina + handoff + score peak
portfolio_v7   collaboratif + cache structurel précédent
portfolio_v6   collaboratif optimisé précédent
portfolio_v5   collaboratif précédent
portfolio_v4   chest-first précédent
portfolio_v3   portfolio score historique
adaptive_v2    planificateur score-aware/ability-aware
heuristic_v1   baseline historique
scalable_v1    grandes cartes / stress tests
```


### `portfolio_v9`

`portfolio_v9` est désormais une **couche minimale au-dessus de `portfolio_v8`**. Les choix de coffres, le cache/validation des routes, le déblocage X/G, les pierres, les machines et le score peak restent ceux de v8. V9 ajoute seulement une affinité de pousseur pour éviter le ping-pong F/M sur le même coffre, un filtrage de relais lorsque le dernier coffre est manipulé avec très peu de stamina, et un staging très conservateur uniquement à la place d'un WAIT de réserve déjà décidé par v8. Voir `docs/PORTFOLIO_V9.md`.

### `portfolio_v8`

`portfolio_v8` conserve les priorités de v7 mais ajoute quatre protections : relais de pousseur en fonction de la stamina, invalidation immédiate d'une route coffre lorsque DIG/CUT modifie le terrain, orientation sûre d'une machine avant tout UNHACK, et conservation du meilleur préfixe de score lorsque poursuivre la trajectoire ferait baisser le score final. Chaque snapshot expose aussi `current_score`, calculé avec la formule officielle. Voir `docs/PORTFOLIO_V8.md`.

### `portfolio_v7`

Version précédente gardée pour comparaison dynamique depuis Godot. Elle conserve le cache structurel et l'orchestration collaborative de v6, mais ne possède pas les protections stamina/route dynamique/score peak de v8. Voir `docs/PORTFOLIO_V7.md`.

### `adaptive_v2`

Le planificateur tient directement compte de la formule de score : en quarts de point, un tick coûte `2`, une stamina dépensée coûte `1` et une batterie dépensée coûte `1`. Il combine :

- A* score-aware pour F/M ;
- capacité spéciale de F sur les trous et de M sur les arbres ;
- planification Sokoban des coffres ;
- routeur de machines avec orientation + rotations + MOVE 2 ticks ;
- analyse marginale des obstacles : un trou/arbre n'est traité que s'il débloque réellement du score ;
- coopération croisée F/X ↔ M/G ;
- anticipation des coffres que les machines autonomes risquent de perdre ;
- interception/hacking préventif ;
- repositionnement sécurisé d'une machine contrôlée lorsqu'elle bloque le plan du partenaire ;
- immobilisation coopérative d'une machine dangereuse pendant qu'une autre termine un déblocage critique ;
- réévaluation à chaque tick.

### `portfolio_v6`

Version précédente de la stratégie chest-first collaborative : plusieurs coffres directs sont répartis entre F et M, les obstacles sont traités par le héros/machine adapté, et tout héros non requis pour un déblocage collecte une pierre ou prépare un autre coffre au lieu d'attendre. Lorsqu'il ne reste que des pierres, les cibles sont affectées conjointement aux deux héros. Les coffres géométriquement impossibles sont écartés afin d'éviter les hacks sans objectif. Voir `docs/PORTFOLIO_V5.md`.

### `portfolio_v3`

Le jeu permet de pré-calculer les actions. `portfolio_v3` exploite cela : il exécute plusieurs planificateurs depuis exactement le même état initial dans le moteur de règles, calcule leur score réel local, puis conserve **le meilleur plan vérifié**. Il inclut toujours `adaptive_v2` et `heuristic_v1`, et ajoute des recherches adaptatives plus larges sur les cartes de taille raisonnable.

Cela garantit dans le moteur local que `portfolio_v3` ne choisit jamais un plan moins bien scoré que les stratégies incluses. Il ne prétend pas résoudre mathématiquement l'optimum global d'un espace d'état arbitrairement grand ; il fournit un optimiseur pratique, déterministe et vérifié par simulation.

## Routes

```text
GET  /api/v1/health
GET  /api/v1/contracts
GET  /api/v1/strategies
GET  /api/v1/settings
PUT  /api/v1/settings
POST /api/v1/settings/reset

POST /api/v1/maps/parse
POST /api/v1/maps/upload

POST /api/v1/simulation-jobs
POST /api/v1/simulation-jobs/upload
GET  /api/v1/simulation-jobs/{job_id}
GET  /api/v1/simulation-jobs/{job_id}/result

POST /api/v1/simulations
POST /api/v1/simulations/upload
POST /api/v1/simulations/replay
POST /api/v1/simulations/replay-text
POST /api/v1/simulations/replay-upload
GET  /api/v1/simulations/{simulation_id}
GET  /api/v1/simulations/{simulation_id}/actions.txt
```

## `actions.txt`

```text
LEFT | LEFT
UP | RIGHT
WAIT | HACK
HACK_MOVE | WAIT
WAIT | WAIT
END_GAME
```

Chaque simulation persiste également :

```text
output/<simulation_id>_actions.txt
```

## Tests et vérifications

```bash
pytest -q
```

La suite vérifie notamment :

- le replay tick-par-tick de l'annexe officielle ;
- parsing/collisions/stamina/batterie/machines/coffres ;
- les capacités spécifiques de F et M ;
- la compatibilité F→Excavator et M→Grappler ;
- le comportement de l'optimiseur sur les cartes de test ;
- les clarifications AlgoMada sur hack/CUT/DIG, buffers entre machines et coffres ;
- une carte mécanique 4x5 contenant tous les éléments ;
- une carte 10x14 correspondant au double de la référence 5x7 ;
- qu'un plan généré se rejoue avec exactement le même score ;
- toutes les routes Swagger ;
- que les multipart sont bien des paramètres `formData` sans `requestBody` dans `/swagger.json` ;
- que `/openapi.json` reste le schéma FastAPI OpenAPI 3 canonique.

## Documents

- `docs/API_CONTRACT.md` : contrat Godot ↔ FastAPI.
- `docs/GDD_INTERPRETATIONS.md` : ambiguïtés du GDD documentées explicitement.


## Intégration Godot 2D

Le frontend minimal utilise par défaut `http://127.0.0.1:8000/api/v1`.

Routes utilisées directement par Godot :

- `GET /health` : test de disponibilité du backend.
- `POST /maps/upload` : validation multipart du `map.txt` sélectionné dans Godot.
- `POST /simulations` : calcul complet de la simulation et des ticks à jouer.
- `GET /settings` : chargement des paramètres persistés.
- `PUT /settings` : sauvegarde des paramètres.
- `POST /settings/reset` : réinitialisation des paramètres.
- `POST /simulations/replay-text` : vérification d'un `actions.txt` déjà calculé.

Les paramètres sont sauvegardés dans `data/settings.json` par défaut.
