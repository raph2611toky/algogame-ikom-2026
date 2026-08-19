# Verification v0.12.0 - GDD Addendum / elevation / Look Ahead

Base: backend supplied on 2026-08-19 (`backend(20260819-092159).zip`).

## Compatibility promise

The historical strategy cores were not rewritten. SHA-256 values remain identical to the supplied backend:

- `strategy_v8.py`: `7c4baf2c12f00b4e75a44ebff918b0b0b34c573d40c4794db3711e504e6593cf`
- `strategy_v9.py`: `76ff611dce5da386b3e5b1aed54d578fbd7d870cd4f7fb407ade58bb8ba92ce5`
- `strategy_v10.py`: `93363ccacfc82424e5d573ce8ac6cc4ef0c6f2c27adc5de68e9f252ecfa21d73`
- `strategy_v11.py`: `4bebb3a8da4b1e39753c12b7b7afac1963b63c7d19ff996e52ac2084aaae7bb5`

`portfolio_v12` inherits V11 -> V10 -> V9 -> V8 and only adds addendum-aware meta-reasoning.

## Elevation compatibility

Validated cases:

- map without `elevation.txt` -> `has_elevation=false`, in-memory zero grid, historical flat movement;
- explicit elevation -> exactly H lines x W digits;
- explicit rock cells must be `0`;
- explicit non-rock cells must be `1..9`;
- uphill hero MOVE: legal for +1/+2 and costs 3 stamina;
- same level MOVE costs 1;
- downhill -1..-4 costs 0 but is not WAIT;
- +3 or more and -5 or less are illegal hero transitions;
- F hole hop / M tree climb compare start altitude directly with landing altitude and keep the special cost 10;
- hero chest push cannot go uphill and costs 5;
- machine MOVE allows absolute elevation delta <=4;
- machine chest uphill push allows +2 but rejects +3;
- chest drop >=5 levels is destroyed before bush/hole resolution.

## Machine Look Ahead

Clarified RIGHT-facing geometry used by runtime and planners:

```text
..3.
.G12
..4.
```

All 1/2/3/4 cells are checked for other machines before a MOVE is queued and again on its completion tick. Normal MOVE does not treat heroes/props as blockers in that scan.

When a chest is directly in front, all six chest Look Ahead cells are checked for machines, and the first three are also checked for F/M. Nearby chest + hero push-priority cases are also covered.

Look Ahead is evaluated before elevation. A blocked automatic machine rotates according to X/G automatic rules; a blocked hacked `HACK_MOVE` becomes an implicit WAIT without rotation and without spending battery when the command cannot even be queued.

## API

Optional elevation is supported by:

- JSON map parse;
- multipart map upload;
- JSON simulation;
- multipart simulation upload;
- JSON simulation jobs;
- multipart simulation job upload;
- replay JSON/text;
- multipart replay upload.

Simulation responses expose `map.elevation_rows` and `map.has_elevation`.

## Verification commands run

Focused addendum/rules/API tests:

```text
pytest -q tests/test_gdd_addendum.py tests/test_rules.py tests/test_machines.py tests/test_map_parser.py tests/test_pathfinding.py tests/test_api.py tests/test_official_replay.py
PASS
```

Current strategy/settings/job integration:

```text
pytest -q tests/test_strategy_v8.py tests/test_strategy_v9.py tests/test_strategy_v10.py tests/test_strategy_v11.py tests/test_strategy_v12.py tests/test_strategies_api.py tests/test_settings.py tests/test_simulation_jobs.py
PASS
```

Additional legacy parser/staff/swagger/core strategy group:

```text
pytest -q tests/test_actions.py tests/test_staff_clarifications.py tests/test_swagger.py tests/test_strategy.py
PASS
```

Manual smoke checks:

```text
LEGACY_AND_ELEVATION_SMOKE_OK
LOOKAHEAD_1_2_3_4_SMOKE_OK
```

The complete suite contains 161 collected tests. Some historical exhaustive portfolio tests are intentionally expensive and were not all completed in one uninterrupted command in this environment; the targeted rule, API, replay, current-strategy and compatibility groups above completed successfully.
