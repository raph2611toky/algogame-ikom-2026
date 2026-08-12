# Vérification backend v0.3.0

## Conformité GDD vérifiée

- alphabet et format `map.txt` ;
- origine `(0,0)` en haut à gauche ;
- déplacements orthogonaux ;
- Ikotofosa : saut d'un trou, Excavator, remplissage des trous ;
- Imahaki : franchissement d'un arbre, Grappler, coupe des arbres ;
- stamina/batterie ;
- MOVE machine sur deux ticks ;
- rotations automatiques X/G ;
- pierres/coffres/cachettes ;
- conflits de poussée ;
- score ;
- `actions.txt` + `END_GAME` ;
- replay de l'annexe officielle.

## Swagger

Routes documentées : 11/11.

La vue `/docs` utilise `/swagger.json` (Swagger 2.0 documentaire généré depuis l'OpenAPI FastAPI réel). Les trois routes multipart sont vérifiées sans `requestBody`, avec paramètres `formData` :

- `/api/v1/maps/upload` ;
- `/api/v1/simulations/upload` ;
- `/api/v1/simulations/replay-upload`.

`/openapi.json` reste l'OpenAPI 3 canonique de FastAPI.

## Tests automatisés

Dernière validation : **32 tests réussis**.

Les tests couvrent entre autres :

- règles et parser ;
- journal officiel 20 ticks ;
- pathfinding et planification de coffres ;
- machines ;
- capacités spécifiques F/M ;
- stratégie adaptive ;
- portfolio ;
- replay exact d'un plan généré ;
- Swagger et multipart ;
- validation des réponses par les mêmes modèles Pydantic exposés dans la documentation.

## Test serveur réel

Uvicorn a été démarré localement et les appels suivants ont répondu `200` :

- `GET /api/v1/health` ;
- `GET /docs` ;
- `GET /swagger.json` ;
- `POST /api/v1/maps/upload` multipart ;
- `POST /api/v1/simulations` JSON.

## Référence carte officielle fournie

Sur `maps/official_sample.txt` :

| Stratégie | Score local | Ticks | Coffres | Pierres | Perdus |
|---|---:|---:|---:|---:|---:|
| `heuristic_v1` | 366 | 57 | 1 | 5 | 0 |
| `adaptive_v2` | 379 | 55 | 1 | 5 | 0 |
| `portfolio_v3` | 379 | 55 | 1 | 5 | 0 |

`portfolio_v3` compare au minimum `adaptive_v2` et `heuristic_v1` dans le moteur de règles et conserve le meilleur résultat. Si les objectifs restent incomplets sur une carte de complexité raisonnable, il lance des variantes de recherche plus larges.

## Portée de l'optimalité

Le backend maximise le score avec des recherches exactes au niveau local (A* score-aware, Sokoban pour les coffres, Dijkstra orientation-aware pour les machines) et un choix de plan vérifié par simulation. Il n'affirme pas un optimum mathématique global pour toutes les cartes arbitraires : l'état conjoint F/M + machines + coffres + environnement dynamique est combinatoire. `portfolio_v3` garantit en revanche de ne pas retenir un plan moins bien scoré que les stratégies qu'il évalue dans ce moteur local.
