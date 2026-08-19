# AlgoGames 2 - GDD Addendum support

Backend version: **0.13.0**

This release adds the second-week `elevation.txt` and machine Look Ahead rules without removing the historical `map.txt` mode or the older strategies.

## 1. Backward compatibility

`MapParser.parse(map_text)` is still valid. If no elevation data is supplied:

- `GameMap.has_elevation == false`;
- the in-memory elevation grid is filled with `0`;
- all historical elevation-free movement remains flat (normal hero MOVE cost 1, no slope restrictions);
- the new machine Look Ahead still applies because it is a new global machine rule, independent of elevation.

All JSON simulation/replay routes accept optional `elevation_text`. All multipart map/simulation/replay/job routes accept optional `elevation_file`.

## 2. Explicit elevation.txt

For a map of `H x W`, `elevation.txt` has exactly `H` lines of exactly `W` digits and no header.

- reachable/non-rock cell: `1..9`;
- rock (`#` in `map.txt`): `0`;
- a `0` on a non-rock cell is rejected;
- a non-zero elevation on a rock is rejected.

The all-zero legacy grid is only an internal compatibility sentinel when no file was supplied.

## 3. Hero elevation rules

- same altitude: normal MOVE costs 1 stamina;
- uphill by 1 or 2: normal MOVE costs 3 stamina;
- uphill by 3 or more: illegal;
- downhill by 1..4: MOVE costs 0 stamina, but is still movement and never counts as WAIT/recovery;
- downhill by 5 or more: illegal;
- Ikotofosa hopping a hole and Imahaki climbing a tree still cost 10 stamina; elevation is compared from the start cell directly to the landing cell after the skipped obstacle;
- hero PUSH advances the hero into the chest's former cell, so that hero step also obeys the +2/-4 movement limits;
- a hero can push a chest only to the same elevation or downhill;
- hero chest PUSH costs 5 stamina per step;
- a chest dropping by 5 or more levels is destroyed before bush/hole resolution, so even a bush cannot save it.

## 4. Machine elevation rules

- a machine MOVE is illegal when `abs(delta_elevation) >= 5`;
- a machine can push a chest uphill by at most 2 levels;
- a machine may push downhill; a chest drop of 5+ levels destroys the chest;
- trees remain physical chest blockers regardless of relative elevation.

## 5. Official machine Look Ahead

Look Ahead is evaluated before elevation and cannot be bypassed by hacking.

For a machine facing RIGHT, the implementation exposes the clarified ordered geometry:

```text
..3.
.G12
..4.
```

- `1`: actual destination cell;
- `2`: two cells ahead;
- `3`: upper side cell beside destination;
- `4`: lower side cell beside destination.

The official GDD's three extra scan cells are `2/3/4`; this backend also explicitly checks `1`, because another machine already occupying the destination is necessarily a collision.

For ordinary movement, only other machines in these cells cancel the move. Heroes, stones, bushes and other non-machine props do not cancel ordinary Look Ahead.

### Chest directly in front

The six-cell chest scan is rotated with machine orientation:

- all six positions are checked for other machines;
- the three positions closest to the chest are additionally checked for F/M;
- if a conflict exists, an automatic machine re-orients; a hacked machine performs an implicit WAIT.

### Nearby chest beside destination

If a chest is adjacent to the machine destination and a hero stands one cell behind that chest in the direction that would push the chest into the machine destination, the hero/chest potential movement has priority and the machine yields.

### Two-tick machine MOVE

The scan is run twice:

1. when a MOVE is queued;
2. again on the completion tick.

If a new machine enters the Look Ahead between those ticks:

- automatic X/G cancels and re-orients using its normal automatic rotation rule;
- hacked `HACK_MOVE` cancels as an implicit WAIT and does **not** re-orient.

## 6. Planner/runtime split

Runtime enforces all collision/elevation rules exactly.

Long-range machine path planners treat current hero positions as dynamic for ordinary planning so that a hero who can move away is not modeled as a permanent wall. Machine-vs-machine Look Ahead and elevation constraints remain part of static machine planning.

## 7. portfolio_v12

`portfolio_v12` inherits the progressive parallel V11/V10 stack. The files `strategy_v8.py`, `strategy_v9.py`, `strategy_v10.py` and `strategy_v11.py` are not rewritten.

V12 adds only addendum-aware meta reasoning:

- V10 relocation/deadlock support now recognizes all official Look Ahead cells instead of the old straight-line buffer approximation;
- autonomous chest-risk prediction includes machine elevation limits and cliff destruction;
- on small maps, if V12 cannot finish under the new machine rules, the service may compare the already-existing V6 candidate under the **same current simulator/rules** and keep the higher-ranked verified trajectory. This is a portfolio fallback, not a rules bypass.

## 8. PUSH stamina clarification

The written original GDD and the new Addendum both state **5 stamina per chest PUSH**. A Discord FAQ message quoted during development says 10 in one example, which conflicts with both written documents. This backend therefore keeps 5, matching the Addendum's explicit "still deplete 5 points of stamina per step" rule. If AlgoMada publishes a newer written correction, change this single rule and its tests together.

## 9. FAQ DIG sur bush + V13

Clarification appliquée : si un Excavator déclenche DIG alors qu'il se trouve sur un bush, le trou est ajouté à l'état mais le bush reste présent et continue à cacher les coffres. Pour la destination d'un coffre, l'ordre de résolution est :

1. destruction par falaise >=5 ;
2. sécurisation par bush ;
3. perte dans un trou ;
4. déplacement normal.

La version 0.13.0 ajoute `portfolio_v13`, documenté dans `docs/PORTFOLIO_V13.md`. V12 et les stratégies historiques restent disponibles et utilisent toujours le même moteur de règles Addendum.
