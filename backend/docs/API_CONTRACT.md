# Contrat Godot ↔ FastAPI — v1.0

## Principe

Godot transmet le contenu exact de `map.txt`. FastAPI parse la carte, calcule une simulation déterministe, puis renvoie :

- l'état initial ;
- la séquence des actions F/M ;
- l'état après chaque tick ;
- les événements ;
- les ressources ;
- le résultat et le score ;
- le contenu final de `actions.txt`.

## Coordonnées

- origine `(0,0)` : coin supérieur gauche ;
- `row` augmente vers le bas ;
- `col` augmente vers la droite.

## Requête principale

`POST /api/v1/simulations`

```json
{
  "mission": {
    "name": "official-sample",
    "map_text": "5 7 100\nG+.M..+\n.###tt#\n.o*.+.@\no##t#tX\n.F#++.."
  },
  "strategy": {
    "name": "heuristic_v1",
    "max_stones_per_hero": 8,
    "max_chest_pairs_per_hero": 6,
    "stuck_end_threshold": 8
  }
}
```

## Réponse principale

La réponse contient notamment :

```json
{
  "contract_version": "1.0",
  "simulation_id": "...",
  "mission_name": "official-sample",
  "map": {
    "height": 5,
    "width": 7,
    "time_limit": 100,
    "rows": ["G+.M..+", ".###tt#", ".o*.+.@", "o##t#tX", ".F#++.."]
  },
  "initial_state": {},
  "ticks": [
    {
      "tick": 1,
      "requested_actions": {"F": "LEFT", "M": "RIGHT"},
      "effective_actions": {"F": "LEFT", "M": "RIGHT"},
      "machine_actions": {"G1": "MOVE", "X1": "CCW"},
      "events": [],
      "state": {}
    }
  ],
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
  "actions": [
    {"tick": 1, "F": "LEFT", "M": "RIGHT"}
  ],
  "actions_txt": "LEFT | RIGHT\nEND_GAME\n",
  "actions_download_url": "/api/v1/simulations/<id>/actions.txt"
}
```

`requested_actions` conserve l'intention de l'IA. `effective_actions` est l'action réellement exécutée par le moteur local après application des règles d'invalidité/WAIT. Le fichier `actions.txt` généré utilise les actions effectives afin de rester cohérent avec le replay local.

## Routes

- `GET /api/v1/health`
- `GET /api/v1/contracts`
- `POST /api/v1/maps/parse`
- `POST /api/v1/maps/upload`
- `POST /api/v1/simulations`
- `POST /api/v1/simulations/upload`
- `POST /api/v1/simulations/replay`
- `POST /api/v1/simulations/replay-text`
- `GET /api/v1/simulations/{simulation_id}`
- `GET /api/v1/simulations/{simulation_id}/actions.txt`

## Intégration Godot

Pour l'intégration vendredi, Godot peut d'abord consommer `ticks` comme un replay calculé à l'avance. Chaque entrée possède déjà l'état complet après le tick : positions, stamina, batterie, pierres, coffres, machines, arbres, trous et événements. La vitesse d'animation Godot ne doit jamais modifier la logique du tick.
