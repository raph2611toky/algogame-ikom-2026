# Vérification backend v0.3.2

## Conformité règles vérifiée

- alphabet et format `map.txt` ;
- origine `(0,0)` en haut à gauche ;
- déplacements orthogonaux ;
- Ikotofosa : saut d'un trou, Excavator, remplissage des trous ;
- Imahaki : franchissement d'un arbre, Grappler, coupe des arbres ;
- stamina et batterie ;
- MOVE machine sur deux ticks ;
- rotations automatiques X/G ;
- hack : suppression des MOVE/rotations automatiques et du DIG de X ;
- CUT de G conservé même lorsque le Grappler est hacké ;
- déplacement simultané de convois de machines de même orientation ;
- réorientation d'une machine automatique si la machine devant elle ne libère pas sa case ;
- protection des coffres lors des mouvements opposés de machines ;
- interdiction d'une poussée héros vers une machine ;
- choix d'un seul héros pour une poussée concurrente dans la stratégie ;
- pierres, coffres, cachettes, trous et arbres ;
- score ;
- `actions.txt` + `END_GAME` ;
- replay de l'annexe officielle ;
- carte mécanique `4x5` ;
- carte d'évaluation `10x14`.

## Swagger

Routes documentées : 11/11.

La vue `/docs` utilise `/swagger.json`. Les trois routes multipart restent exposées sans `requestBody`, avec paramètres `formData` :

- `/api/v1/maps/upload` ;
- `/api/v1/simulations/upload` ;
- `/api/v1/simulations/replay-upload`.

`/openapi.json` reste le schéma OpenAPI canonique de FastAPI.

## Tests automatisés

Dernière validation : **45 tests réussis**.

La suite couvre le moteur, le replay officiel, les stratégies, le Swagger, les clarifications AlgoMada sur les machines et les coffres, ainsi que les cartes `4x5` et `10x14`.

## Référence carte officielle fournie

| Stratégie | Score local | Ticks | Coffres | Pierres | Perdus |
|---|---:|---:|---:|---:|---:|
| `heuristic_v1` | 366 | 57 | 1 | 5 | 0 |
| `adaptive_v2` | 380 | 55 | 1 | 5 | 0 |
| `portfolio_v3` | 380 | 55 | 1 | 5 | 0 |

`portfolio_v3` compare les plans dans le même moteur corrigé et conserve le meilleur résultat local.
