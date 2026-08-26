# KAKAFANDODO — backend Co-player Twist 2

Backend FastAPI autoritaire pour la version coopérative à deux joueurs. Le frontend envoie les intentions d’Ikotofosa et d’Imahaki ; le backend valide la carte, les mouvements simultanés, le relief, la stamina, les HP, le soin, le portage, le bruit, les machines, la perception et l’IA du gardien. Les animations ne modifient jamais l’état logique.

## Installation

Python 3.11 ou plus récent est requis.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[test]'
uvicorn app.main:app --reload
```

Ouvrir ensuite :

- API : `http://127.0.0.1:8000/api/v1/health`
- Swagger : `http://127.0.0.1:8000/docs`
- contrat frontend : `http://127.0.0.1:8000/api/v1/contracts`

Le script `./run.sh` démarre également le serveur. Les variables `KAKAFANDODO_HOST`, `KAKAFANDODO_PORT` et `KAKAFANDODO_CORS_ORIGINS` permettent de modifier le lancement.

## Structure

```text
app/
├── api/routes/          # REST, WebSocket, santé et contrats
├── core/                # configuration d’exécution
├── domain/              # état métier, actions et enums
├── engine/              # règles, perception, pathfinding, simulateur
│   └── guard_ai/        # easy, medium, hard
├── schemas/             # entrées/sorties Pydantic
└── services/            # sessions, séquences et replay
maps/demo/               # exemple map.txt + elevation.txt
tests/                   # tests unitaires et API
docs/                    # décisions explicites du GDD
```

## Format de carte

La première ligne est `H W TIME_LIMIT_SECONDS`, suivie de `H` lignes de largeur `W`.

```text
. vide      F Ikotofosa    M Imahaki      K gardien
# rocher    t arbre         o trou          @ cachette
X excav.    G grappler      + pierre         * coffre
E sortie coopérative optionnelle
```

`F`, `M` et `K` sont obligatoires et uniques. `elevation.txt` est optionnel, contient une valeur `0..9` par cellule, impose `0` sur les rochers et `1..9` ailleurs. L’ajout `E` rend la condition « les deux héros sortent ensemble » explicite ; sans `E`, finir les objectifs termine la mission pour compatibilité.

## Workflow REST

Créer une partie :

```bash
jq -Rs '{map_text: ., difficulty: "hard", seed: 42}' maps/demo/map.txt |
curl -s http://127.0.0.1:8000/api/v1/games \
  -H 'Content-Type: application/json' -d @-
```

Puis envoyer un tick numéroté :

```bash
curl -s http://127.0.0.1:8000/api/v1/games/GAME_ID/ticks \
  -H 'Content-Type: application/json' \
  -d '{
    "sequence": 1,
    "actions": {
      "F": {"action": "RUN", "direction": "RIGHT"},
      "M": {"action": "WAIT"}
    }
  }'
```

Chaque réponse contient l’état validé, la progression, les cooldowns, l’intention du gardien et une liste d’événements à animer. Réenvoyer la même `sequence` retourne exactement le résultat mémorisé avec `duplicate: true`; sauter un numéro retourne HTTP 409.

Le WebSocket `/api/v1/games/{game_id}/ws` accepte le même JSON qu’un tick REST. Le premier message du serveur est toujours le snapshot courant.

## Endpoints

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/api/v1/health` | disponibilité et nombre de parties |
| `GET` | `/api/v1/contracts` | symboles, actions, IA et recommandations |
| `GET` | `/api/v1/ai/profiles` | description des trois difficultés |
| `POST` | `/api/v1/maps/validate` | valide map et élévations sans créer de partie |
| `POST` | `/api/v1/games` | crée une session |
| `GET` | `/api/v1/games/{id}` | snapshot courant |
| `POST` | `/api/v1/games/{id}/ticks` | applique deux intentions simultanées |
| `POST` | `/api/v1/games/{id}/reset` | rejoue la seed depuis le début |
| `DELETE` | `/api/v1/games/{id}` | libère la session |
| `POST` | `/api/v1/replays` | exécute une liste de ticks hors temps réel |
| `WS` | `/api/v1/games/{id}/ws` | boucle temps réel bidirectionnelle |

## IA du gardien

- `easy` : `WAIT` ou direction légale pseudo-aléatoire ; même seed = même partie.
- `medium` : cible visible, dernière position connue, bruit entendu, puis patrouille ; A* sans anticipation.
- `hard` : sélection tactique de cible visible, A*, puis carte de croyance probabiliste lorsque la cible disparaît. Cette IA ne consulte jamais la position actuelle d’un héros invisible.

La perception reste commune aux trois niveaux : cône de vision avec occlusion, jauge de détection, bruit temporaire, dernière position connue et modes `PATROL`, `INVESTIGATE`, `CHASE`, `SEARCH`.

## Tests

```bash
python3 -m pytest -q
```

La suite vérifie notamment le parsing, les élévations, les seuils HP/vitesse, les collisions simultanées, le soin, le remboursement d’un soin interrompu, le portage réciproque, le saut assisté, les impacts, la fenêtre de secours, les coffres, les machines, l’information partielle et l’idempotence réseau.

## Valeurs et décisions configurables

Les valeurs du GDD sont les valeurs par défaut : 100 HP, dégâts de 20, soin de 20, vitesse F 110 %, M 100 %, gardien 80/100/120 %, machine 155 %, portage 82,5 %. Une partie peut fournir un objet `balance` pour les modifier.

Les points non verrouillés par le GDD sont rendus explicites dans [docs/GDD_DECISIONS.md](docs/GDD_DECISIONS.md). `telemetry_score` est un indicateur interne inspiré de l’ancien jeu, pas une nouvelle règle officielle du Twist 2.
