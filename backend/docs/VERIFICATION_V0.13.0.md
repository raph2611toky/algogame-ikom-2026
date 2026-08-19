# Vérification v0.13.0 — V13 global/predictif

Base : backend utilisateur du 2026-08-19, avec GDD original + GDD Addendum + clarifications FAQ fournies dans la conversation.

## Changements fonctionnels

- ajout de `portfolio_v13` et passage en stratégie par défaut ;
- `DIG` d'un Excavator sur un bush conserve le bush comme cachette ;
- résolution coffre : falaise >=5 > bush > hole > déplacement normal ;
- planner coffre compatible avec `hole+bush` ;
- mode V13 strict pour éviter un PUSH planifié vers une machine actuellement derrière le coffre, sans modifier le comportement legacy des anciennes stratégies ;
- ranking direct V13 fondé sur le coût réel en quarts de score ;
- tâches machines estimées avec les vrais planners score/elevation/look-ahead au lieu de Manhattan ;
- ranking global coffre = déblocage + push final + ressources + synergies + urgence ;
- prévision des machines autonomes par le Simulator réel ;
- validation temporelle bornée des micro-plans d'une machine déjà hackée ;
- activation du cœur V10/V11/V12 sur les cartes <=160 sans le shortcut séparé V9 ;
- arrêt immédiat lorsque les objectifs sont finis ;
- portfolio borné de candidats forts ;
- fallback scalable pour les cartes >160 cellules.

## Règles Addendum conservées

- élévation explicite : reachable `1..9`, rock `0` ;
- héros : +1/+2 autorisé à 3 stamina, +3 interdit, descente -1..-4 à 0 stamina mais sans récupération, -5 interdit ;
- machines : différence absolue <=4 ;
- héros : coffre jamais uphill ; machine : coffre uphill au plus +2 ;
- chute de coffre >=5 : destruction même sur bush ;
- saut de F / escalade de M : altitude calculée départ -> landing ;
- Look Ahead avant l'élévation et prioritaire sur HACK_MOVE ;
- recheck du Look Ahead au tick d'exécution d'un MOVE machine.

## Tests ciblés exécutés

```text
pytest -q tests/test_actions.py tests/test_gdd_addendum.py \
  tests/test_staff_clarifications.py tests/test_rules.py tests/test_machines.py \
  tests/test_map_parser.py tests/test_pathfinding.py tests/test_official_replay.py
PASS
```

```text
pytest -q tests/test_strategy_v8.py tests/test_strategy_v9.py
PASS
```

```text
pytest -q tests/test_strategy_v10.py tests/test_strategy_v11.py \
  tests/test_strategy_v12.py tests/test_strategy_v13.py
PASS
```

```text
pytest -q tests/test_strategies_api.py tests/test_settings.py tests/test_api.py \
  tests/test_swagger.py tests/test_simulation_jobs.py
PASS
```

Certains tests historiques exhaustifs (`portfolio_v3` sur plusieurs grandes cartes) sont très coûteux et ne sont pas utilisés pour valider la logique V13. Ils n'ont pas été forcés jusqu'au bout dans cet environnement.

## Benchmarks de référence observés

Les nombres ci-dessous sont des vérifications locales du backend, pas une promesse de score sur les hidden maps :

- `official_sample.txt` + `official_sample_elevation.txt` : objectifs terminés, 1 coffre, 5 pierres, 0 coffre perdu ;
- `evaluation_10x14.txt` : objectifs terminés, 1 coffre, 2 pierres, 0 coffre perdu ;
- carte de régression 10x14 à deux coffres : objectifs terminés, 2 coffres, 6 pierres, 0 coffre perdu.

Le score final officiel reste celui obtenu en rejouant `actions.txt` dans le Game Runner AlgoMada. Dès que ce runner est fourni, utiliser `scripts/differential_runner.py` (ou adapter son wrapper JSON) pour détecter la première divergence.
