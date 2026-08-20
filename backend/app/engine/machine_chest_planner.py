from __future__ import annotations

"""Machine-assisted treasure-chest planning for AlgoGames 2.

The original planners intentionally kept two concerns separate:

* ``machine_planner`` moves a hacked X/G to a position or obstacle;
* ``chest_planner`` lets F/M push a chest to a bush.

Elevation makes that separation incomplete because only a machine may push a
chest uphill (by at most +2).  This module plans the missing compound action:
reposition a *hacked* compatible machine around a chest, push it one or more
times, reposition again when the route turns, and finally deliver it to a bush.

It does not replace the Simulator or Rules.  The returned plan is structural and
is revalidated at execution time so the official dynamic Look Ahead remains the
source of truth when other machines move during the two-tick HACK_MOVE.
"""

from copy import deepcopy
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from app.domain.enums import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    DIRECTION_TO_ORIENTATION,
    DIRECTION_VECTORS,
    ORIENTATION_TO_DIRECTION,
    Direction,
    HeroAction,
    MachineKind,
    Orientation,
)
from app.domain.models import GameState, MachineState, Position
from app.engine.machine_planner import plan_machine_to_position
from app.engine.rules import Rules
from app.engine.score_pathfinding import score_cost_units


@dataclass(frozen=True, slots=True)
class MachineChestPlan:
    machine_id: str
    chest_start: Position
    bush: Position
    actions: tuple[HeroAction, ...]
    ticks: int
    battery_cost: int
    pushes: int
    structural_lookahead_risk: bool = False

    @property
    def score_cost_units(self) -> int:
        return score_cost_units(self.ticks, 0, self.battery_cost)


@dataclass(frozen=True, slots=True)
class _PushNode:
    machine_position: Position
    machine_orientation: Orientation
    chest_position: Position


@dataclass(frozen=True, slots=True)
class _Edge:
    actions: tuple[HeroAction, ...]
    ticks: int
    battery: int
    structural_risk: bool


@dataclass(frozen=True, slots=True)
class _Cost:
    units: int
    ticks: int
    battery: int
    pushes: int
    structural_risks: int


def _forward(position: Position, orientation: Orientation) -> Position:
    direction = ORIENTATION_TO_DIRECTION[orientation]
    dr, dc = DIRECTION_VECTORS[direction]
    return position.moved(dr, dc)


def _orientation_after(actions: tuple[HeroAction, ...], start: Orientation) -> Orientation:
    orientation = start
    for action in actions:
        if action == HeroAction.HACK_CW:
            orientation = CLOCKWISE[orientation]
        elif action == HeroAction.HACK_CCW:
            orientation = COUNTER_CLOCKWISE[orientation]
    return orientation


def _rotation_actions(current: Orientation, target: Orientation) -> tuple[HeroAction, ...]:
    if current == target:
        return ()
    if CLOCKWISE[current] == target:
        return (HeroAction.HACK_CW,)
    if COUNTER_CLOCKWISE[current] == target:
        return (HeroAction.HACK_CCW,)
    # Opposite direction: deterministic two-CW rotation.  Cost is identical to
    # two CCW actions and keeping one convention makes plans reproducible.
    return (HeroAction.HACK_CW, HeroAction.HACK_CW)


def _working_state(
    state: GameState,
    machine_id: str,
    node: _PushNode,
    original_chest: Position,
) -> GameState:
    work = deepcopy(state)
    machine = work.machines[machine_id]
    machine.position = node.machine_position
    machine.orientation = node.machine_orientation
    machine.pending_move = False
    machine.auto_move_pending = False

    # Only the target chest is hypothetical.  Every other chest keeps its real
    # location and remains a hard obstacle for repositioning / pushing.
    work.chests.discard(original_chest)
    work.chests.add(node.chest_position)

    # A hacked hero rides the controlled machine.  Keeping the controller on the
    # machine also mirrors the actual Simulator state for later validation.
    if machine.hacked_by is not None:
        hero = work.heroes[machine.hacked_by]
        hero.position = node.machine_position
        hero.hacking_machine_id = machine_id
    return work


def _structural_push_valid(
    state: GameState,
    machine: MachineState,
    chest_from: Position,
    chest_to: Position,
    *,
    original_chest: Position,
) -> bool:
    """Terrain/elevation legality without freezing temporary Look Ahead actors."""
    if not state.game_map.in_bounds(chest_to):
        return False
    if chest_to in state.game_map.rocks or chest_to in state.trees:
        return False

    other_chests = set(state.chests)
    other_chests.discard(original_chest)
    other_chests.discard(chest_from)
    if chest_to in other_chests:
        return False

    # Intentional plans never sacrifice a chest.  Hole+Bush remains safe per the
    # FAQ; a normal hole is a permanent loss and is therefore rejected.
    if chest_to in state.holes and chest_to not in state.game_map.bushes:
        return False
    if Rules.chest_destroyed_by_cliff(state, chest_from, chest_to):
        return False
    if Rules.machine_chest_elevation_reason(state, chest_from, chest_to) is not None:
        return False
    if Rules.machine_elevation_reason(state, machine.position, chest_from) is not None:
        return False
    return True


def _reconstruct(
    parent: dict[_PushNode, tuple[_PushNode, _Edge]],
    start: _PushNode,
    node: _PushNode,
    final_edge: _Edge,
) -> tuple[tuple[HeroAction, ...], int, int, int, bool]:
    edges: list[_Edge] = [final_edge]
    cursor = node
    while cursor != start:
        previous, edge = parent[cursor]
        edges.append(edge)
        cursor = previous
    edges.reverse()
    actions: list[HeroAction] = []
    ticks = 0
    battery = 0
    risks = 0
    for edge in edges:
        actions.extend(edge.actions)
        ticks += edge.ticks
        battery += edge.battery
        risks += int(edge.structural_risk)
    return tuple(actions), ticks, battery, len(edges), bool(risks)


def plan_machine_chest_to_bush(
    state: GameState,
    machine: MachineState,
    chest: Position,
    bush: Position,
    *,
    max_expansions: int = 160,
    reposition_expansions: int = 4500,
    allow_structural_lookahead_retry: bool = True,
) -> MachineChestPlan | None:
    """Plan a hacked machine from its current state to hide ``chest`` in ``bush``.

    Search nodes are *push states*, not individual machine moves.  For every
    possible next push the existing machine A* is used to reach the required
    behind-the-chest cell.  This keeps the search compact while preserving all
    existing movement/elevation/tree/hole semantics.

    The strict reposition attempt respects current machine Look Ahead.  When the
    only blocker is another machine's *current* position, a structural retry is
    allowed and marked as risky.  Runtime V14 then re-plans/WAITs if the official
    two-tick Look Ahead still blocks the action.
    """
    if chest not in state.chests or bush not in state.game_map.bushes:
        return None
    if machine.id not in state.machines:
        return None

    start = _PushNode(machine.position, machine.orientation, chest)
    serial = count()
    # priority, units, ticks, battery, pushes, risks, serial, node
    heap: list[tuple[int, int, int, int, int, int, int, _PushNode]] = [
        (5 * chest.manhattan(bush), 0, 0, 0, 0, 0, next(serial), start)
    ]
    best: dict[_PushNode, _Cost] = {start: _Cost(0, 0, 0, 0, 0)}
    parent: dict[_PushNode, tuple[_PushNode, _Edge]] = {}
    expansions = 0

    # Cache the expensive inner reposition planner.  The topology is fixed for a
    # single call; node+behind therefore fully describe the structural query.
    reposition_cache: dict[tuple[_PushNode, Position, bool], tuple[tuple[HeroAction, ...], int, int, Orientation] | None] = {}

    while heap and expansions < max_expansions:
        _priority, units, ticks, battery, pushes, risks, _serial, node = heappop(heap)
        if best.get(node) != _Cost(units, ticks, battery, pushes, risks):
            continue
        expansions += 1

        work = _working_state(state, machine.id, node, chest)
        work_machine = work.machines[machine.id]

        for direction in Direction:
            dr, dc = DIRECTION_VECTORS[direction]
            desired_orientation = DIRECTION_TO_ORIENTATION[direction]
            behind = node.chest_position.moved(-dr, -dc)
            chest_to = node.chest_position.moved(dr, dc)

            if not work.game_map.in_bounds(behind) or behind in work.game_map.rocks:
                continue
            if behind in work.chests and behind != node.chest_position:
                continue
            if work.machine_at(behind) is not None and work.machine_at(behind).id != machine.id:
                continue
            if work_machine.kind == MachineKind.EXCAVATOR and behind in work.trees:
                continue
            if work_machine.kind == MachineKind.GRAPPLER and behind in work.holes:
                continue

            # The pusher must be able to move from the behind cell into the current
            # chest cell; this constraint is separate from chest elevation.
            if Rules.machine_elevation_reason(work, behind, node.chest_position) is not None:
                continue

            strict_key = (node, behind, False)
            reposition = reposition_cache.get(strict_key)
            if strict_key not in reposition_cache:
                plan = plan_machine_to_position(
                    work,
                    work_machine,
                    behind,
                    max_expansions=reposition_expansions,
                    ignore_other_machines=False,
                )
                if plan is None:
                    reposition_cache[strict_key] = None
                else:
                    end_orientation = _orientation_after(plan.actions, node.machine_orientation)
                    reposition_cache[strict_key] = (
                        plan.actions,
                        plan.ticks,
                        plan.battery_cost,
                        end_orientation,
                    )
                reposition = reposition_cache[strict_key]

            structural_risk = False
            if reposition is None and allow_structural_lookahead_retry:
                loose_key = (node, behind, True)
                reposition = reposition_cache.get(loose_key)
                if loose_key not in reposition_cache:
                    plan = plan_machine_to_position(
                        work,
                        work_machine,
                        behind,
                        max_expansions=reposition_expansions,
                        ignore_other_machines=True,
                    )
                    if plan is None:
                        reposition_cache[loose_key] = None
                    else:
                        end_orientation = _orientation_after(plan.actions, node.machine_orientation)
                        reposition_cache[loose_key] = (
                            plan.actions,
                            plan.ticks,
                            plan.battery_cost,
                            end_orientation,
                        )
                    reposition = reposition_cache[loose_key]
                structural_risk = reposition is not None
            if reposition is None:
                continue

            reposition_actions, reposition_ticks, reposition_battery, end_orientation = reposition
            rotations = _rotation_actions(end_orientation, desired_orientation)

            hypothetical_machine = deepcopy(work_machine)
            hypothetical_machine.position = behind
            hypothetical_machine.orientation = desired_orientation
            if not _structural_push_valid(
                work,
                hypothetical_machine,
                node.chest_position,
                chest_to,
                original_chest=chest,
            ):
                continue

            # A strict dynamic Look Ahead check is useful when it succeeds.  A
            # failure is not considered structurally impossible because the other
            # machines/heroes may move before this future push; mark the edge so V14
            # can penalize it and revalidate at execution time.
            check_state = _working_state(state, machine.id, node, chest)
            check_machine = check_state.machines[machine.id]
            check_machine.position = behind
            check_machine.orientation = desired_orientation
            strict_push = Rules.machine_can_push_chest(
                check_state,
                check_machine,
                node.chest_position,
                ignore_machines=False,
            )
            if not strict_push:
                structural_risk = True

            # HACK_MOVE queues on one tick and completes on the following WAIT.
            push_actions = (HeroAction.HACK_MOVE, HeroAction.WAIT)
            edge_actions = tuple(reposition_actions) + rotations + push_actions
            edge_ticks = reposition_ticks + len(rotations) + 2
            edge_battery = reposition_battery + len(rotations) + 1
            edge = _Edge(edge_actions, edge_ticks, edge_battery, structural_risk)

            if chest_to == bush:
                actions, total_ticks, total_battery, total_pushes, any_risk = _reconstruct(
                    parent, start, node, edge
                )
                return MachineChestPlan(
                    machine_id=machine.id,
                    chest_start=chest,
                    bush=bush,
                    actions=actions,
                    ticks=total_ticks,
                    battery_cost=total_battery,
                    pushes=total_pushes,
                    structural_lookahead_risk=any_risk,
                )

            next_node = _PushNode(node.chest_position, desired_orientation, chest_to)
            new_ticks = ticks + edge_ticks
            new_battery = battery + edge_battery
            new_pushes = pushes + 1
            new_risks = risks + int(structural_risk)
            new_units = score_cost_units(new_ticks, 0, new_battery) + 35 * new_risks
            new_cost = _Cost(new_units, new_ticks, new_battery, new_pushes, new_risks)
            old = best.get(next_node)
            if old is not None and (
                old.units,
                old.ticks,
                old.battery,
                old.structural_risks,
            ) <= (
                new_cost.units,
                new_cost.ticks,
                new_cost.battery,
                new_cost.structural_risks,
            ):
                continue
            best[next_node] = new_cost
            parent[next_node] = (node, edge)
            heuristic = 5 * chest_to.manhattan(bush)
            heappush(
                heap,
                (
                    new_units + heuristic,
                    new_units,
                    new_ticks,
                    new_battery,
                    new_pushes,
                    new_risks,
                    next(serial),
                    next_node,
                ),
            )

    return None
