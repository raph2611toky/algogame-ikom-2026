# Contrat Godot ↔ FastAPI — v1.0

## Principe

Godot transmet `map.txt`. FastAPI renvoie l'état initial, les actions F/M, chaque état de tick, les événements, les ressources, le résultat, le score et le contenu de `actions.txt`.

Coordonnées : origine `(0,0)` en haut à gauche, `row` vers le bas, `col` vers la droite.

## Documentation de référence

```text
/docs          Swagger UI complet
/swagger.json  vue Swagger 2.0 documentaire
/openapi.json  OpenAPI 3.1 canonique généré par FastAPI
/redoc         ReDoc sur l'OpenAPI canonique
```

La vue Swagger 2.0 est générée depuis le vrai OpenAPI FastAPI afin de présenter les endpoints multipart sous forme de paramètres manuels `formData`, sans bloc `requestBody`.

## Requête principale

`POST /api/v1/simulations`

```json
{
  "mission": {
    "name": "official-sample",
    "map_text": "5 7 100\nG+.M..+\n.###tt#\n.o*.+.@\no##t#tX\n.F#++.."
  },
  "strategy": {
    "name": "portfolio_v3",
    "max_stones_per_hero": 16,
    "max_chest_pairs_per_hero": 12,
    "max_unlock_obstacles": 20,
    "unlock_pair_candidates": 8,
    "stuck_end_threshold": 8
  }
}
```

`portfolio_v3` est la valeur par défaut. `adaptive_v2` et `heuristic_v1` restent disponibles pour comparaison.

## Réponse principale

Le schéma exact est `SimulationResponse` et est exposé par Swagger. Structure :

```json
{
  "contract_version": "1.0",
  "simulation_id": "...",
  "mission_name": "official-sample",
  "map": {
    "height": 5,
    "width": 7,
    "time_limit": 100,
    "rows": ["G+.M..+", ".###tt#", ".o*.+.@", "o##t#tX", ".F#++.."],
    "coordinate_system": {
      "origin": "top-left",
      "row_increases": "down",
      "col_increases": "right"
    }
  },
  "initial_state": {},
  "ticks": [],
  "result": {
    "score": 0,
    "stones_collected": 0,
    "chests_secured": 0,
    "chests_lost": 0,
    "remaining_time": 0,
    "total_stamina": 0,
    "total_battery": 0,
    "end_reason": "OBJECTIVES_FINISHED"
  },
  "actions": [],
  "actions_txt": "END_GAME\n",
  "actions_download_url": "/api/v1/simulations/<id>/actions.txt"
}
```

Les objets `initial_state`, `ticks`, `heroes`, `machines`, `props` et `events` sont entièrement typés dans Swagger ; les `{}`/`[]` ci-dessus ne servent qu'à garder ce document court.

`requested_actions` garde la décision demandée. `effective_actions` garde ce que le moteur a réellement exécuté après validation/coercition en `WAIT`. `actions.txt` utilise les actions effectives.

## Multipart sans Request Body dans Swagger

### `POST /api/v1/maps/upload`

Paramètre manuel :

```text
file : file, requis
```

### `POST /api/v1/simulations/upload`

```text
file          : file, requis
name          : string, optionnel
strategy_json : string JSON, optionnel
```

Le nom réel du paramètre est `strategy_json`.

### `POST /api/v1/simulations/replay-upload`

```text
map_file                       : file, requis
actions_file                   : file, requis
name                           : string, optionnel
stop_when_objectives_finished  : boolean, optionnel
```

## Routes complètes

```text
GET  /api/v1/health
GET  /api/v1/contracts
POST /api/v1/maps/parse
POST /api/v1/maps/upload
POST /api/v1/simulations
POST /api/v1/simulations/upload
POST /api/v1/simulations/replay
POST /api/v1/simulations/replay-text
POST /api/v1/simulations/replay-upload
GET  /api/v1/simulations/{simulation_id}
GET  /api/v1/simulations/{simulation_id}/actions.txt
```

## Intégration Godot

Godot peut consommer `ticks` comme une simulation pré-calculée. La vitesse visuelle et les contrôles du replay ne doivent pas modifier la logique calculée par FastAPI.
