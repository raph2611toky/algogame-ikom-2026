from __future__ import annotations

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
    HeroAction,
    HeroId,
    MachineKind,
    Orientation,
)
from app.domain.models import GameState, Position
from app.engine.machine_planner import MachineControlPlan, plan_machine_to_position
from app.engine.rules import Rules
from app.engine.strategy_v10 import _MachineHazard
from app.engine.strategy_v11 import ProgressiveParallelPortfolioStrategy


@dataclass(slots=True)
class _JointEscapeCommitment:
    """Small addendum-only choreography for two hacked machines.

    Each entry is a *tick-level* pair of hero actions.  MOVE entries are always
    followed by an explicit WAIT tick so the 2-tick machine movement is allowed
    to complete and the official look-ahead is re-evaluated by the simulator.
    """

    actions: list[dict[HeroId, HeroAction]]
    machine_ids: tuple[str, str]
    created_tick: int


class AddendumAwareParallelPortfolioStrategy(ProgressiveParallelPortfolioStrategy):
    """portfolio_v12 = v11/v10 core + second-week rule awareness.

    The existing V8/V9/V10/V11 strategy files are intentionally left untouched.
    V12 only adapts two pieces of *meta reasoning* whose old implementation used
    the pre-addendum machine buffer approximation:

    1. relocation/deadlock detection now uses the official 4-cell movement
       look-ahead and 6-cell chest-push look-ahead;
    2. autonomous chest-hazard prediction understands elevation, including the
       machine +2 uphill chest limit and >=5 downhill cliff destruction;
    3. when the official look-ahead creates a genuine two-machine stand-off, a
       bounded joint escape search temporarily parks the machines so the V10/V11
       planner can resume. This activates only after the inherited resolver has
       already failed while both heroes are hacking and waiting.

    Direct hero routes, chest planning, progressive parallelism, relay stamina,
    opportunity scheduling and micro-plan commitment remain inherited.
    """

    JOINT_ESCAPE_MAX_TICKS = 14
    JOINT_ESCAPE_MAX_EXPANSIONS = 700
    JOINT_ESCAPE_GOAL_PLAN_EXPANSIONS = 5000

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._joint_escape: _JointEscapeCommitment | None = None

    def _relocation_plan(
        self,
        state: GameState,
        controller_id: HeroId,
        partner_obstacles: set[Position],
    ) -> tuple[Position, MachineControlPlan] | None:
        controller = state.heroes[controller_id]
        if not controller.is_hacking or controller.hacking_machine_id is None or not partner_obstacles:
            return None
        machine = state.machines[controller.hacking_machine_id]
        partner_id = self._other(controller_id)
        partner_kind = MachineKind.EXCAVATOR if partner_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER

        close = []
        for partner_machine in state.machines.values():
            if partner_machine.kind != partner_kind or partner_machine.id == machine.id:
                continue

            scanned = set(Rules.machine_move_lookahead_positions(partner_machine))
            if Rules.machine_forward(partner_machine) in state.chests:
                first_three, extra_three = Rules.machine_chest_lookahead_positions(partner_machine)
                scanned.update(first_three)
                scanned.update(extra_three)
            if machine.position in scanned:
                close.append(partner_machine)

        if not close or machine.pending_move or controller.battery <= 0:
            return None
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return None

        positions = [
            pos
            for pos in state.game_map.all_positions()
            if 1 <= machine.position.manhattan(pos) <= 2 and pos not in state.game_map.rocks
        ]
        positions.sort(
            key=lambda pos: (
                -min((pos.manhattan(m.position) for m in close), default=0),
                -min((pos.manhattan(o) for o in partner_obstacles), default=0),
                machine.position.manhattan(pos),
                pos.row,
                pos.col,
            )
        )
        best = None
        for target in positions[:10]:
            control = plan_machine_to_position(state, machine, target, max_expansions=5000)
            if control is None or not control.actions or control.battery_cost > controller.battery:
                continue
            rank = (
                control.ticks,
                control.score_cost_units,
                -min(target.manhattan(m.position) for m in close),
                target.row,
                target.col,
            )
            if best is None or rank < best[0]:
                best = (rank, target, control)
        if best is None:
            return None
        return best[1], best[2]

    # ------------------------------------------------------------------
    # Addendum-only joint machine escape.
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_move_target(position: Position, orientation: Orientation) -> Position:
        direction = ORIENTATION_TO_DIRECTION[orientation]
        dr, dc = DIRECTION_VECTORS[direction]
        return position.moved(dr, dc)

    def _escape_move_legal(
        self,
        state: GameState,
        machine_id: str,
        position: Position,
        orientation: Orientation,
        other_position: Position,
    ) -> bool:
        """Conservative MOVE used only by the bounded deadlock escape search.

        The escape never pushes chests and never deliberately enters a tree.  It
        therefore cannot change objective topology while trying to yield space.
        The actual simulator remains the source of truth and rechecks look-ahead
        again on both ticks of HACK_MOVE.
        """
        target = self._escape_move_target(position, orientation)
        if not state.game_map.in_bounds(target):
            return False
        if target in state.game_map.rocks or target in state.chests:
            return False
        machine = state.machines[machine_id]
        if machine.kind == MachineKind.EXCAVATOR and target in state.trees:
            return False
        if machine.kind == MachineKind.GRAPPLER and (target in state.holes or target in state.trees):
            return False
        if Rules.machine_elevation_reason(state, position, target) is not None:
            return False
        # The clarified 1/2/3/4 scan includes the destination itself.  For an
        # escape MOVE there is no chest in front, so the ordinary 4-cell scan is
        # the complete hardcoded collision guard.
        scanned = Rules.machine_move_lookahead_positions(
            machine,
            position=position,
            orientation=orientation,
        )
        return other_position not in scanned

    def _required_obstacles_for_joint_escape(
        self,
        state: GameState,
    ) -> tuple[tuple[Position, ...], tuple[Position, ...]]:
        target = self._target_chest if self._target_chest in state.chests else None
        if target is None:
            return (), ()
        if state.game_map.height * state.game_map.width > 160:
            profiles = self._viable_profiles(state)
            profile = profiles.get(target) or self._unlock_profile(state, target)
        else:
            profile = self._unlock_profile(state, target)
        holes, trees = self._expanded_unlock_obstacles(state, profile)
        # Only current, real obstacles are goals.  Hypothetical prerequisites
        # remain the responsibility of the existing V10 opportunity scheduler.
        live_holes = tuple(sorted(pos for pos in holes if pos in state.holes))
        live_trees = tuple(sorted(pos for pos in trees if pos in state.trees))
        return live_holes, live_trees

    def _local_productive_machine_path_exists(
        self,
        state: GameState,
        machine_id: str,
        start: Position,
        other_position: Position,
        obstacles: tuple[Position, ...],
        *,
        max_moves: int = 3,
    ) -> bool:
        """Cheap local proof that the normal planner can make progress again.

        Rotations are free for this *reachability proof* (the real planner still
        charges their tick/battery cost).  Every MOVE itself obeys the official
        four-cell look-ahead, elevation and machine-specific terrain rules.
        """
        if not obstacles:
            return False
        machine = state.machines[machine_id]
        obstacle_set = set(obstacles)

        def goal(position: Position) -> bool:
            if machine.kind == MachineKind.EXCAVATOR:
                # X fills a hole from an adjacent cell.
                return any(position.manhattan(obstacle) == 1 for obstacle in obstacle_set)
            # G cuts by entering the tree cell.
            return position in obstacle_set

        if goal(start):
            return True
        frontier: list[tuple[Position, int]] = [(start, 0)]
        seen = {start}
        cursor = 0
        while cursor < len(frontier):
            position, depth = frontier[cursor]
            cursor += 1
            if depth >= max_moves:
                continue
            for direction, (dr, dc) in DIRECTION_VECTORS.items():
                orientation = DIRECTION_TO_ORIENTATION[direction]
                target = position.moved(dr, dc)
                if not state.game_map.in_bounds(target):
                    continue
                if target in state.game_map.rocks or target in state.chests:
                    continue
                if machine.kind == MachineKind.EXCAVATOR and target in state.trees:
                    continue
                if machine.kind == MachineKind.GRAPPLER:
                    if target in state.holes:
                        continue
                    # Do not mutate unrelated trees while merely parking.  The
                    # target tree itself is the productive endpoint and is okay.
                    if target in state.trees and target not in obstacle_set:
                        continue
                if Rules.machine_elevation_reason(state, position, target) is not None:
                    continue
                scanned = Rules.machine_move_lookahead_positions(
                    machine,
                    position=position,
                    orientation=orientation,
                )
                if other_position in scanned:
                    continue
                if target in seen:
                    continue
                if goal(target):
                    return True
                seen.add(target)
                frontier.append((target, depth + 1))
        return False

    def _joint_goal_available(
        self,
        state: GameState,
        machine_ids: tuple[str, str],
        node: tuple[tuple[Position, Orientation], tuple[Position, Orientation]],
        holes: tuple[Position, ...],
        trees: tuple[Position, ...],
        escape_battery_used: dict[str, int],
    ) -> bool:
        for index, machine_id in enumerate(machine_ids):
            machine = state.machines[machine_id]
            hero_id = machine.hacked_by
            if hero_id is None:
                continue
            remaining_battery = state.heroes[hero_id].battery - escape_battery_used.get(machine_id, 0)
            if remaining_battery <= 0:
                continue
            obstacles = holes if machine.kind == MachineKind.EXCAVATOR else trees
            if not obstacles:
                continue
            position = node[index][0]
            other_position = node[1 - index][0]
            if self._local_productive_machine_path_exists(
                state,
                machine_id,
                position,
                other_position,
                obstacles,
                max_moves=3,
            ):
                return True
        return False

    def _plan_joint_escape(self, state: GameState) -> list[tuple[str, HeroAction]] | None:
        """Find a short legal yielding choreography for the two ridden machines.

        This is deliberately *not* a replacement for the machine planner.  The
        search only rotates/moves the currently hacked machines without touching
        chests or terrain, and stops as soon as the normal planner becomes viable
        again for one of the target chest's real obstacles.
        """
        f = state.heroes[HeroId.IKOTOFOSA]
        m = state.heroes[HeroId.IMAHAKI]
        if not (f.is_hacking and m.is_hacking and f.hacking_machine_id and m.hacking_machine_id):
            return None
        if f.hacking_machine_id == m.hacking_machine_id:
            return None
        machine_ids = (f.hacking_machine_id, m.hacking_machine_id)
        machines = tuple(state.machines[mid] for mid in machine_ids)
        if any(machine.pending_move for machine in machines):
            return None

        holes, trees = self._required_obstacles_for_joint_escape(state)
        if not holes and not trees:
            return None

        start = tuple((machine.position, machine.orientation) for machine in machines)
        # heap item: score ticks, active actions, sequence id, node, path,
        # battery counts per machine
        serial = count()
        heap: list[tuple[int, int, int, object, list[tuple[str, HeroAction]], dict[str, int]]] = []
        heappush(heap, (0, 0, next(serial), start, [], {machine_ids[0]: 0, machine_ids[1]: 0}))
        best: dict[object, tuple[int, int]] = {start: (0, 0)}
        expansions = 0

        while heap and expansions < self.JOINT_ESCAPE_MAX_EXPANSIONS:
            ticks, action_count, _serial, node_obj, path, battery_used = heappop(heap)
            node = node_obj  # type: ignore[assignment]
            if best.get(node) != (ticks, action_count):
                continue
            expansions += 1

            if path and self._joint_goal_available(
                state,
                machine_ids,
                node,
                holes,
                trees,
                battery_used,
            ):
                return path
            if ticks >= self.JOINT_ESCAPE_MAX_TICKS:
                continue

            for index, machine_id in enumerate(machine_ids):
                position, orientation = node[index]
                other_position = node[1 - index][0]
                hero_id = state.machines[machine_id].hacked_by
                if hero_id is None:
                    continue
                hero = state.heroes[hero_id]
                used = battery_used[machine_id]
                if used >= hero.battery:
                    continue

                for action, new_orientation in (
                    (HeroAction.HACK_CW, CLOCKWISE[orientation]),
                    (HeroAction.HACK_CCW, COUNTER_CLOCKWISE[orientation]),
                ):
                    nticks = ticks + 1
                    if nticks > self.JOINT_ESCAPE_MAX_TICKS:
                        continue
                    new_node_list = list(node)
                    new_node_list[index] = (position, new_orientation)
                    new_node = tuple(new_node_list)
                    rank = (nticks, action_count + 1)
                    if best.get(new_node) is not None and best[new_node] <= rank:
                        continue
                    best[new_node] = rank
                    used2 = dict(battery_used)
                    used2[machine_id] += 1
                    heappush(
                        heap,
                        (
                            nticks,
                            action_count + 1,
                            next(serial),
                            new_node,
                            path + [(machine_id, action)],
                            used2,
                        ),
                    )

                if self._escape_move_legal(state, machine_id, position, orientation, other_position):
                    nticks = ticks + 2
                    if nticks <= self.JOINT_ESCAPE_MAX_TICKS:
                        target = self._escape_move_target(position, orientation)
                        new_node_list = list(node)
                        new_node_list[index] = (target, orientation)
                        new_node = tuple(new_node_list)
                        rank = (nticks, action_count + 1)
                        if best.get(new_node) is None or rank < best[new_node]:
                            best[new_node] = rank
                            used2 = dict(battery_used)
                            used2[machine_id] += 1
                            heappush(
                                heap,
                                (
                                    nticks,
                                    action_count + 1,
                                    next(serial),
                                    new_node,
                                    path + [(machine_id, HeroAction.HACK_MOVE)],
                                    used2,
                                ),
                            )
        return None

    def _install_joint_escape(self, state: GameState, path: list[tuple[str, HeroAction]]) -> bool:
        if not path:
            return False
        actions: list[dict[HeroId, HeroAction]] = []
        machine_ids: list[str] = []
        for machine_id, action in path:
            machine = state.machines.get(machine_id)
            if machine is None or machine.hacked_by is None:
                return False
            hero_id = machine.hacked_by
            machine_ids.append(machine_id)
            pair = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
            pair[hero_id] = action
            actions.append(pair)
            if action == HeroAction.HACK_MOVE:
                # The second tick is intentionally idle. The simulator rechecks
                # the hardcoded look-ahead before completing the movement.
                actions.append({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT})

        mids = tuple(dict.fromkeys(machine_ids))
        if len(mids) != 2:
            return False
        self._joint_escape = _JointEscapeCommitment(actions=actions, machine_ids=(mids[0], mids[1]), created_tick=state.elapsed)
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            self._drop_commitment(hero_id)
        for machine_id in mids:
            self._rotation_state.pop(machine_id, None)
            self._rotation_block_until.pop(machine_id, None)
        return True

    def _continue_joint_escape(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
    ) -> bool:
        commitment = self._joint_escape
        if commitment is None:
            return False
        # Any unhack, unexpected pending state before an active operation, or
        # depleted battery invalidates the choreography and returns control to V10.
        for machine_id in commitment.machine_ids:
            machine = state.machines.get(machine_id)
            if machine is None or machine.hacked_by is None:
                self._joint_escape = None
                return False
        if not commitment.actions:
            self._joint_escape = None
            self._target_selection_signature = None
            self._opportunity_signature = None
            self._deadlock_ticks = 0
            return False

        pair = commitment.actions.pop(0)
        for hero_id, action in pair.items():
            if action in {HeroAction.HACK_CW, HeroAction.HACK_CCW, HeroAction.HACK_MOVE}:
                hero = state.heroes[hero_id]
                if not hero.is_hacking or hero.battery <= 0 or hero.hacking_machine_id is None:
                    self._joint_escape = None
                    return False
                machine = state.machines[hero.hacking_machine_id]
                if action == HeroAction.HACK_MOVE:
                    if machine.pending_move or not Rules.machine_forward_queueable(state, machine):
                        self._joint_escape = None
                        self._target_selection_signature = None
                        self._opportunity_signature = None
                        return False
            decisions[hero_id] = action
            if action != HeroAction.WAIT:
                self.last_decisions[hero_id.value] = 'echappement conjoint look-ahead addendum'
        return True

    def _deadlock_resolver(self, state: GameState, decisions: dict[HeroId, HeroAction]) -> None:
        # A previously planned choreography is a tiny transaction: finish it
        # before allowing V10/V11 to undo the yielding rotations on the next tick.
        if self._continue_joint_escape(state, decisions):
            return

        # Give the preserved V10 resolver the first opportunity. It handles the
        # common one-machine relocation case more cheaply and remains unchanged.
        super()._deadlock_resolver(state, decisions)
        if any(decisions.get(hero_id, HeroAction.WAIT) != HeroAction.WAIT for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI)):
            return
        if not state.chests or not all(state.heroes[hero_id].is_hacking for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI)):
            return
        if self._deadlock_ticks < self.DEADLOCK_TICKS:
            return

        path = self._plan_joint_escape(state)
        if path is None or not self._install_joint_escape(state, path):
            return
        self._deadlock_ticks = 0
        self._continue_joint_escape(state, decisions)

    def _predict_autonomous_hazard(
        self,
        state: GameState,
        machine_id: str,
        *,
        orientation: Orientation | None = None,
        horizon: int | None = None,
    ) -> _MachineHazard | None:
        """V10 hazard simulation updated to the current official rules.

        Other machines are kept at their current positions, as in V10. Heroes
        are deliberately ignored in the *future* hazard projection: if a hero is
        still behind a chest at runtime, the simulator's official look-ahead will
        give the hero priority anyway; ignoring that temporary protection here
        avoids declaring a dangerous machine permanently safe.
        """
        machine_real = state.machines.get(machine_id)
        if machine_real is None:
            return None
        horizon = horizon or self.AUTONOMOUS_HAZARD_HORIZON
        signature = ("v12", self._hazard_signature(state, machine_id, orientation), int(horizon))
        if signature in self._hazard_cache:
            return self._hazard_cache[signature]

        simulation = deepcopy(state)
        machine = simulation.machines[machine_id]
        machine.hacked_by = None
        machine.pending_move = False
        machine.auto_move_pending = False
        machine.resume_delay = 0
        if orientation is not None:
            machine.orientation = orientation

        result: _MachineHazard | None = None
        trace: list[Position] = [machine.position]

        def rotate_blocked() -> None:
            machine.orientation = (
                COUNTER_CLOCKWISE[machine.orientation]
                if machine.kind == MachineKind.EXCAVATOR
                else CLOCKWISE[machine.orientation]
            )

        for decision_index in range(1, horizon + 1):
            if machine.kind == MachineKind.GRAPPLER and machine.position in simulation.trees:
                simulation.trees.remove(machine.position)
                continue

            if machine.kind == MachineKind.EXCAVATOR and machine.steps_since_dig >= 5:
                simulation.holes.add(machine.position)
                machine.steps_since_dig = 0
                continue

            # Official hardcoded look-ahead is checked before elevation. For the
            # long-horizon prediction only other machines matter; heroes are not
            # treated as static walls.
            if Rules.machine_lookahead_reason(simulation, machine, check_heroes=False) is not None:
                rotate_blocked()
                continue

            target = Rules.machine_forward(machine)
            if not Rules.machine_cell_passable(simulation, machine, target):
                rotate_blocked()
                continue

            if target in simulation.chests:
                direction = ORIENTATION_TO_DIRECTION[machine.orientation]
                dr, dc = DIRECTION_VECTORS[direction]
                destination = target.moved(dr, dc)

                blocked = (
                    not simulation.game_map.in_bounds(destination)
                    or destination in simulation.game_map.rocks
                    or destination in simulation.trees
                    or destination in simulation.chests
                    or simulation.machine_at(destination) is not None
                    or Rules.machine_chest_elevation_reason(simulation, target, destination) is not None
                )
                if blocked:
                    rotate_blocked()
                    continue

                if Rules.chest_destroyed_by_cliff(simulation, target, destination):
                    result = _MachineHazard(
                        machine_id,
                        120000,
                        decision_index,
                        target,
                        destination,
                        "coffre detruit par falaise >=5 niveaux",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

                # FAQ: DIG on a bush keeps the bush as a hiding spot.  Therefore
                # bush has priority over a co-located hole; cliff destruction was
                # already checked above and remains stronger than both.
                if destination in simulation.holes and destination not in simulation.game_map.bushes:
                    result = _MachineHazard(
                        machine_id,
                        100000,
                        decision_index,
                        target,
                        destination,
                        "coffre pousse dans un trou",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

                simulation.chests.remove(target)
                if destination in simulation.game_map.bushes:
                    machine.position = target
                    trace.append(machine.position)
                    if machine.kind == MachineKind.EXCAVATOR:
                        machine.steps_since_dig += 1
                    continue

                simulation.chests.add(destination)
                if self._is_non_bush_boundary(simulation, destination):
                    result = _MachineHazard(
                        machine_id,
                        90000,
                        decision_index,
                        target,
                        destination,
                        "coffre pousse vers un bord non recuperable",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

                before = min((target.manhattan(b) for b in simulation.game_map.bushes), default=0)
                after = min((destination.manhattan(b) for b in simulation.game_map.bushes), default=0)
                if after >= before + 4:
                    result = _MachineHazard(
                        machine_id,
                        25000,
                        decision_index,
                        target,
                        destination,
                        "coffre fortement eloigne d'une cachette",
                        tuple(dict.fromkeys(reversed(trace[-10:]))),
                    )
                    break

            machine.position = target
            trace.append(machine.position)
            if machine.kind == MachineKind.EXCAVATOR:
                machine.steps_since_dig += 1

        self._hazard_cache[signature] = result
        if len(self._hazard_cache) > 512:
            self._hazard_cache.clear()
            self._hazard_cache[signature] = result
        return result
