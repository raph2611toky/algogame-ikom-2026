from __future__ import annotations

"""V14 global mission planner.

V14 keeps V13/V12 as the safety net and adds the missing *intentional* use of
machines for uphill chest pushes.  The planner works at mission level so F and M
are assigned together instead of greedily one after the other.

The low-level Simulator/Rules remain authoritative.  Every cached action is
validated immediately before execution and machine plans are rebuilt after a
hack or any dynamic Look Ahead interruption.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Iterable

from app.domain.enums import (
    ACTION_TO_DIRECTION,
    DIRECTION_VECTORS,
    HeroAction,
    HeroId,
    MachineKind,
    PUSH_ACTIONS,
)
from app.domain.models import GameState, Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.machine_chest_planner import MachineChestPlan, plan_machine_chest_to_bush
from app.engine.pathfinding import hero_neighbors
from app.engine.rules import Rules
from app.engine.simulator import Simulator
from app.engine.score_pathfinding import find_score_path, score_cost_units
from app.engine.strategy_v13 import PredictiveGlobalPortfolioStrategy


@dataclass(frozen=True, slots=True)
class MissionCandidate:
    hero_id: HeroId
    kind: str
    target_key: tuple[object, ...]
    description: str
    utility_units: int
    estimated_ticks: int
    estimated_stamina: int = 0
    estimated_battery: int = 0
    actions: tuple[HeroAction, ...] = ()
    target_position: Position | None = None
    chest: Position | None = None
    bush: Position | None = None
    machine_id: str | None = None
    structural_risk: bool = False


@dataclass(slots=True)
class MissionCommitment:
    candidate: MissionCandidate
    actions: list[HeroAction] = field(default_factory=list)
    created_tick: int = 0
    secured_at_start: int = 0
    lost_at_start: int = 0
    expected_chest: Position | None = None
    pending_chest_to: Position | None = None
    blocked_ticks: int = 0
    replans: int = 0
    release_after_rotation: bool = False


class GlobalMissionPortfolioStrategy(PredictiveGlobalPortfolioStrategy):
    """V14: machine-assisted chest missions + joint F/M assignment.

    Key policy changes:
    - no global "stones first" gate;
    - direct chest, machine chest, stones and carried-machine stones always
      compete in the same utility scale;
    - machine chests include approach, HACK, battery and expected stamina
      recovery while riding;
    - F/M missions are chosen as a pair using parallel wall-clock cost;
    - low stamina receives a non-linear reserve penalty to avoid exhausting a
      hero before high-value chests are solved;
    - active machine plans are revalidated every HACK_MOVE, preserving official
      dynamic Look Ahead priority.
    """

    CHEST_REWARD_UNITS = 600
    STONE_REWARD_UNITS = 100
    MACHINE_RISK_PENALTY = 45
    REGION_OVERLAP_PENALTY = 36
    MAX_DIRECT_PER_HERO = 5
    MAX_STONES_PER_HERO_V14 = 6
    MAX_MACHINE_CHEST_COMBOS = 10
    MAX_PAIR_CANDIDATES = 8
    MAX_MACHINE_BLOCKED_TICKS = 5
    MAX_MACHINE_REPLANS = 5

    def __init__(self, *, planning_bias: str = "score", medium_mode: bool = False, **kwargs) -> None:
        super().__init__(planning_bias=planning_bias, **kwargs)
        self.medium_mode = medium_mode
        self._v14_missions: dict[HeroId, MissionCommitment] = {}
        self._v14_no_mission_ticks = 0
        self._v14_assignment_signature: tuple[object, ...] | None = None
        self._v14_last_assignment_tick = -1

    # ------------------------------------------------------------------
    # Utility model
    # ------------------------------------------------------------------

    @staticmethod
    def _reserve_penalty(stamina: int) -> int:
        """Planning-only future-value penalty; not part of the official score."""
        stamina = max(0, min(100, stamina))
        if stamina >= 40:
            return 0
        if stamina >= 20:
            return (40 - stamina) * 2
        if stamina >= 10:
            return 40 + (20 - stamina) * 5
        return 90 + (10 - stamina) * 10

    @staticmethod
    def _path_stones(state: GameState, start: Position, steps: Iterable) -> int:
        pos = start
        seen: set[Position] = set()
        for step in steps:
            pos = step.destination
            if pos in state.stones:
                seen.add(pos)
        return len(seen)

    @staticmethod
    def _mission_chest_key(candidate: MissionCandidate) -> tuple[int, int] | None:
        if candidate.chest is None:
            return None
        return candidate.chest.row, candidate.chest.col

    @staticmethod
    def _mission_machine_key(candidate: MissionCandidate) -> str | None:
        return candidate.machine_id

    @staticmethod
    def _compatible_kind(hero_id: HeroId) -> MachineKind:
        return MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER

    def _recovery_adjustment(self, stamina_needed: int, current: int) -> tuple[int, int, int]:
        if stamina_needed > 100:
            return 10_000, 0, 100_000
        deficit = max(0, stamina_needed - current)
        wait_ticks = deficit * 2
        recovered = deficit
        # Time cost minus the official final-stamina credit recovered by waiting.
        extra_units = max(0, 2 * wait_ticks - recovered)
        return wait_ticks, recovered, extra_units

    # ------------------------------------------------------------------
    # Candidate generation
    # ------------------------------------------------------------------

    def _direct_candidates(self, state: GameState, hero_id: HeroId) -> list[MissionCandidate]:
        if not state.chests or not state.game_map.bushes:
            return []
        hero = state.heroes[hero_id]
        pairs: list[tuple[int, Position, Position]] = []
        bushes_all = sorted(state.game_map.bushes)
        for chest in sorted(state.chests):
            bushes = sorted(bushes_all, key=lambda b: (chest.manhattan(b), b.row, b.col))
            limit = min(len(bushes), 3 if self.medium_mode else len(bushes))
            for bush in bushes[:limit]:
                pairs.append((hero.position.manhattan(chest) + chest.manhattan(bush), chest, bush))
        pairs.sort(key=lambda row: (row[0], row[1].row, row[1].col, row[2].row, row[2].col))

        cell_count = state.game_map.height * state.game_map.width
        expansion_budget = 9_000 if cell_count <= 400 else 5_000
        attempt_budget = 10 if self.medium_mode else 16
        result: list[MissionCandidate] = []
        for _approx, chest, bush in pairs[:attempt_budget]:
            plan = plan_chest_to_bush(
                state,
                hero_id,
                chest,
                bush,
                max_expansions=expansion_budget,
                optimize_for_score=True,
                avoid_machine_push_destinations=True,
            )
            if plan is None or not plan.actions or plan.stamina_cost > 100:
                continue
            wait_ticks, recovered, wait_units = self._recovery_adjustment(plan.stamina_cost, hero.stamina)
            projected = min(100, hero.stamina + recovered) - plan.stamina_cost
            side_stone_positions: set[Position] = set()
            # The direct chest plan can contain ordinary/jump movement before and
            # between pushes. Count only robustly known move destinations.
            pos = hero.position
            for action in plan.actions:
                if action in PUSH_ACTIONS:
                    dr, dc = Rules.direction_delta(action)
                    pos = pos.moved(dr, dc)
                    if pos in state.stones:
                        side_stone_positions.add(pos)
                    continue
                if action in {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}:
                    step = next((s for s in hero_neighbors(state, hero_id, pos) if s.action == action), None)
                    if step is not None:
                        pos = step.destination
                        if pos in state.stones:
                            side_stone_positions.add(pos)
            utility = (
                self.CHEST_REWARD_UNITS
                + min(len(side_stone_positions), 3) * self.STONE_REWARD_UNITS
                - plan.score_cost_units
                - wait_units
                - self._reserve_penalty(projected)
            )
            if utility <= 0:
                continue
            result.append(
                MissionCandidate(
                    hero_id=hero_id,
                    kind="direct_chest",
                    target_key=("direct_chest", chest.row, chest.col, bush.row, bush.col),
                    description=f"coffre direct ({chest.row},{chest.col}) -> ({bush.row},{bush.col})",
                    utility_units=utility,
                    estimated_ticks=plan.ticks + wait_ticks,
                    estimated_stamina=plan.stamina_cost,
                    actions=plan.actions,
                    target_position=chest,
                    chest=chest,
                    bush=bush,
                )
            )
        result.sort(key=lambda c: (-c.utility_units, c.estimated_ticks, c.description))
        return result[: self.MAX_DIRECT_PER_HERO]

    def _stone_candidates_v14(self, state: GameState, hero_id: HeroId) -> list[MissionCandidate]:
        if not state.stones:
            return []
        hero = state.heroes[hero_id]
        stones = sorted(state.stones, key=lambda p: (hero.position.manhattan(p), p.row, p.col))
        stones = stones[: min(self.MAX_STONES_PER_HERO_V14, len(stones))]
        limit = 12_000 if state.game_map.height * state.game_map.width <= 400 else 6_000
        result: list[MissionCandidate] = []
        for stone in stones:
            path = find_score_path(state, hero_id, stone, max_expansions=limit)
            if path is None or not path.steps or path.total_stamina_cost > 100:
                continue
            wait_ticks, recovered, wait_units = self._recovery_adjustment(path.total_stamina_cost, hero.stamina)
            projected = min(100, hero.stamina + recovered) - path.total_stamina_cost
            collected = max(1, self._path_stones(state, hero.position, path.steps))
            utility = (
                collected * self.STONE_REWARD_UNITS
                - score_cost_units(path.ticks, path.total_stamina_cost)
                - wait_units
                - self._reserve_penalty(projected)
            )
            if utility <= 0:
                continue
            result.append(
                MissionCandidate(
                    hero_id=hero_id,
                    kind="stone",
                    target_key=("stone", stone.row, stone.col),
                    description=f"pierre ({stone.row},{stone.col})",
                    utility_units=utility,
                    estimated_ticks=path.ticks + wait_ticks,
                    estimated_stamina=path.total_stamina_cost,
                    actions=tuple(step.action for step in path.steps),
                    target_position=stone,
                )
            )
        result.sort(key=lambda c: (-c.utility_units, c.estimated_ticks, c.description))
        return result[: self.MAX_STONES_PER_HERO_V14]

    def _machine_stone_candidates_v14(self, state: GameState, hero_id: HeroId) -> list[MissionCandidate]:
        hero = state.heroes[hero_id]
        result: list[MissionCandidate] = []
        machines = [m for m in state.machines.values() if m.carried_stones > 0]
        machines.sort(key=lambda m: (hero.position.manhattan(m.position), m.id))
        for machine in machines[:3]:
            path = find_score_path(state, hero_id, machine.position, max_expansions=10_000)
            if path is None or not path.steps or path.total_stamina_cost > 100:
                continue
            wait_ticks, recovered, wait_units = self._recovery_adjustment(path.total_stamina_cost, hero.stamina)
            projected = min(100, hero.stamina + recovered) - path.total_stamina_cost
            utility = (
                machine.carried_stones * self.STONE_REWARD_UNITS
                - score_cost_units(path.ticks, path.total_stamina_cost)
                - wait_units
                - self._reserve_penalty(projected)
            )
            if utility <= 0:
                continue
            result.append(
                MissionCandidate(
                    hero_id=hero_id,
                    kind="machine_stones",
                    target_key=("machine_stones", machine.id),
                    description=f"recuperer {machine.carried_stones} pierre(s) de {machine.id}",
                    utility_units=utility,
                    estimated_ticks=path.ticks + wait_ticks,
                    estimated_stamina=path.total_stamina_cost,
                    actions=tuple(step.action for step in path.steps),
                    target_position=machine.position,
                    machine_id=machine.id,
                )
            )
        return result

    def _machine_chest_candidates(self, state: GameState, hero_id: HeroId) -> list[MissionCandidate]:
        if not state.chests or not state.game_map.bushes:
            return []
        hero = state.heroes[hero_id]
        if hero.battery <= 1:
            return []
        kind = self._compatible_kind(hero_id)
        machines = [
            m for m in state.machines.values()
            if m.kind == kind and (not m.is_hacked or m.hacked_by == hero_id)
        ]
        if hero.is_hacking:
            machines = [m for m in machines if m.id == hero.hacking_machine_id]
        if not machines:
            return []

        combos: list[tuple[int, str, Position, Position]] = []
        for machine in machines:
            for chest in state.chests:
                bushes = sorted(state.game_map.bushes, key=lambda b: (chest.manhattan(b), b.row, b.col))
                bush_limit = min(len(bushes), 3 if self.medium_mode else len(bushes))
                for bush in bushes[:bush_limit]:
                    approach_approx = 0 if hero.hacking_machine_id == machine.id else hero.position.manhattan(machine.position)
                    combos.append((approach_approx + machine.position.manhattan(chest) + chest.manhattan(bush), machine.id, chest, bush))
        combos.sort(key=lambda row: (row[0], row[1], row[2].row, row[2].col, row[3].row, row[3].col))
        combos = combos[: self.MAX_MACHINE_CHEST_COMBOS]

        result: list[MissionCandidate] = []
        cell_count = state.game_map.height * state.game_map.width
        outer_expansions = 110 if cell_count <= 400 else 65
        reposition_expansions = 2800 if cell_count <= 400 else 1600

        for _approx, machine_id, chest, bush in combos:
            machine = state.machines[machine_id]
            plan = plan_machine_chest_to_bush(
                state,
                machine,
                chest,
                bush,
                max_expansions=outer_expansions,
                reposition_expansions=reposition_expansions,
            )
            if plan is None:
                continue

            if hero.hacking_machine_id == machine_id:
                approach_ticks = 0
                approach_stamina = 0
                hack_ticks = 0
                hack_battery = 0
            else:
                approach = find_score_path(state, hero_id, machine.position, max_expansions=12_000)
                if approach is None or approach.total_stamina_cost > 100:
                    continue
                approach_ticks = approach.ticks
                approach_stamina = approach.total_stamina_cost
                hack_ticks = 1
                hack_battery = 1

            wait_ticks, recovered_before, wait_units = self._recovery_adjustment(approach_stamina, hero.stamina)
            stamina_after_approach = min(100, hero.stamina + recovered_before) - approach_stamina
            hacking_ticks = hack_ticks + plan.ticks
            riding_recovery = min(100 - stamina_after_approach, hacking_ticks // 2)
            projected_stamina = stamina_after_approach + riding_recovery
            total_battery = hack_battery + plan.battery_cost
            if total_battery > hero.battery:
                continue
            total_ticks = wait_ticks + approach_ticks + hacking_ticks
            if total_ticks >= state.remaining_time:
                continue
            cost = (
                score_cost_units(approach_ticks + hacking_ticks, approach_stamina, total_battery)
                + wait_units
                - riding_recovery
            )
            risk = self.MACHINE_RISK_PENALTY if plan.structural_lookahead_risk else 0
            utility = self.CHEST_REWARD_UNITS - cost - risk - self._reserve_penalty(projected_stamina)
            if utility <= 0:
                continue
            result.append(
                MissionCandidate(
                    hero_id=hero_id,
                    kind="machine_chest",
                    target_key=("machine_chest", machine_id, chest.row, chest.col, bush.row, bush.col),
                    description=f"{machine_id} pousse coffre ({chest.row},{chest.col}) -> ({bush.row},{bush.col})",
                    utility_units=utility,
                    estimated_ticks=total_ticks,
                    estimated_stamina=approach_stamina,
                    estimated_battery=total_battery,
                    target_position=chest,
                    chest=chest,
                    bush=bush,
                    machine_id=machine_id,
                    structural_risk=plan.structural_lookahead_risk,
                )
            )
        result.sort(key=lambda c: (-c.utility_units, c.estimated_ticks, c.estimated_battery, c.description))
        return result[:5]

    def _mission_candidates(self, state: GameState, hero_id: HeroId) -> list[MissionCandidate]:
        candidates: list[MissionCandidate] = []
        candidates.extend(self._direct_candidates(state, hero_id))
        candidates.extend(self._machine_chest_candidates(state, hero_id))
        candidates.extend(self._stone_candidates_v14(state, hero_id))
        candidates.extend(self._machine_stone_candidates_v14(state, hero_id))
        candidates.sort(key=lambda c: (-c.utility_units, c.estimated_ticks, c.description))
        return candidates[: self.MAX_PAIR_CANDIDATES]

    # ------------------------------------------------------------------
    # Joint assignment / regional deconfliction
    # ------------------------------------------------------------------

    def _pair_utility(self, f: MissionCandidate | None, m: MissionCandidate | None) -> int | None:
        if f is None and m is None:
            return None
        if f is not None and m is not None:
            f_chest = self._mission_chest_key(f)
            m_chest = self._mission_chest_key(m)
            if f_chest is not None and f_chest == m_chest:
                return None
            if f.machine_id is not None and f.machine_id == m.machine_id:
                return None

        utility = (f.utility_units if f else 0) + (m.utility_units if m else 0)
        if f is not None and m is not None:
            # Individual utilities each paid their own time. In parallel the score
            # loses time only once, so credit the overlapped wall-clock duration.
            utility += 2 * min(f.estimated_ticks, m.estimated_ticks)
            if f.target_position is not None and m.target_position is not None:
                distance = f.target_position.manhattan(m.target_position)
                if distance <= 3:
                    utility -= self.REGION_OVERLAP_PENALTY * (4 - distance)
        return utility

    def _reserved_conflict(self, candidate: MissionCandidate, commitments: dict[HeroId, MissionCommitment]) -> bool:
        c_chest = candidate.chest
        for commitment in commitments.values():
            other = commitment.candidate
            # Chest coordinates change after every PUSH.  Compare against the
            # commitment's live expected position, not only its creation key, so
            # the free hero does not "steal" the same physical chest mid-route.
            reserved_chest = commitment.expected_chest or other.chest
            if c_chest is not None and reserved_chest is not None and c_chest == reserved_chest:
                return True
            if candidate.machine_id is not None and candidate.machine_id == other.machine_id:
                return True
            if candidate.target_key == other.target_key:
                return True
        return False

    def _install(self, state: GameState, candidate: MissionCandidate) -> None:
        self._v14_missions[candidate.hero_id] = MissionCommitment(
            candidate=candidate,
            actions=list(candidate.actions),
            created_tick=state.elapsed,
            secured_at_start=state.secured_chests,
            lost_at_start=state.lost_chests,
            expected_chest=candidate.chest,
        )
        self.last_decisions[candidate.hero_id.value] = candidate.description

    def _assign_free_heroes(self, state: GameState) -> None:
        free = [hid for hid in (HeroId.IKOTOFOSA, HeroId.IMAHAKI) if hid not in self._v14_missions]
        if not free:
            return

        # If both are free, select the pair globally.  If one is committed, the
        # other independently takes the best non-conflicting mission.
        if len(free) == 2:
            f_candidates = self._mission_candidates(state, HeroId.IKOTOFOSA)
            m_candidates = self._mission_candidates(state, HeroId.IMAHAKI)
            # If every remaining chest currently needs an obstacle-unlock sequence
            # that is not representable as a direct or machine-push mission, do
            # not let a positive stone detour hide it.  V13 already owns the
            # proven X/FILL + G/CUT prerequisite logic, so deliberately delegate
            # this state to the inherited controller immediately.
            if state.chests and not any(
                candidate.kind in {"direct_chest", "machine_chest"}
                for candidate in (*f_candidates, *m_candidates)
            ):
                return
            best: tuple[int, MissionCandidate | None, MissionCandidate | None] | None = None
            for f in [None, *f_candidates]:
                for m in [None, *m_candidates]:
                    value = self._pair_utility(f, m)
                    if value is None or value <= 0:
                        continue
                    rank = (value, int(f is not None) + int(m is not None))
                    if best is None or rank > (best[0], int(best[1] is not None) + int(best[2] is not None)):
                        best = (value, f, m)
            if best is not None:
                if best[1] is not None:
                    self._install(state, best[1])
                if best[2] is not None:
                    self._install(state, best[2])
                self._v14_no_mission_ticks = 0
                self._v14_last_assignment_tick = state.elapsed
            return

        hero_id = free[0]
        reserved_chests = {
            commitment.expected_chest
            for commitment in self._v14_missions.values()
            if commitment.expected_chest is not None
        }
        if state.chests and set(state.chests).issubset(reserved_chests):
            # The active partner already owns every remaining chest.  Avoid the
            # expensive chest/machine-chest planners and give the free hero only
            # genuinely independent side work.
            candidates = self._stone_candidates_v14(state, hero_id)
            candidates.extend(self._machine_stone_candidates_v14(state, hero_id))
            candidates.sort(key=lambda c: (-c.utility_units, c.estimated_ticks, c.description))
        else:
            candidates = self._mission_candidates(state, hero_id)
        for candidate in candidates:
            if self._reserved_conflict(candidate, self._v14_missions):
                continue
            if candidate.utility_units <= 0:
                continue
            self._install(state, candidate)
            self._v14_no_mission_ticks = 0
            self._v14_last_assignment_tick = state.elapsed
            return

    # ------------------------------------------------------------------
    # Commitment lifecycle / execution
    # ------------------------------------------------------------------

    def _drop_mission(self, hero_id: HeroId) -> None:
        self._v14_missions.pop(hero_id, None)

    def _reconcile_machine_chest(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> bool:
        candidate = commitment.candidate
        if candidate.machine_id not in state.machines:
            self._drop_mission(hero_id)
            return False
        if commitment.pending_chest_to is not None:
            machine = state.machines[candidate.machine_id]
            # HACK_MOVE is a two-tick action.  Immediately after queueing, the
            # chest is still at its old cell and ``pending_move`` is True; do not
            # mistake that legitimate wait tick for a Look Ahead cancellation.
            if machine.pending_move:
                return True
            old = commitment.expected_chest
            destination = commitment.pending_chest_to
            if destination in state.chests:
                commitment.expected_chest = destination
                commitment.pending_chest_to = None
                commitment.blocked_ticks = 0
                # Keep the remaining structural suffix.  Every future HACK_MOVE is
                # still revalidated against the live Rules/Look Ahead, so a full
                # replan after every successful push is unnecessary and expensive.
            elif destination == candidate.bush and (old is None or old not in state.chests):
                self._drop_mission(hero_id)
                return False
            elif old is not None and old in state.chests:
                # Second-tick Look Ahead blocked the queued push. Keep the chest
                # identity, discard the stale control suffix and try again.
                commitment.pending_chest_to = None
                commitment.actions.clear()
                commitment.blocked_ticks += 1
            else:
                self._drop_mission(hero_id)
                return False
        elif commitment.expected_chest is not None and commitment.expected_chest not in state.chests:
            # The target was moved by another actor before our own queued push.
            self._drop_mission(hero_id)
            return False
        return True

    def _reconcile(self, state: GameState) -> None:
        for hero_id, commitment in list(self._v14_missions.items()):
            kind = commitment.candidate.kind
            if kind == "stone":
                target = commitment.candidate.target_position
                if target is None or target not in state.stones:
                    self._drop_mission(hero_id)
            elif kind == "machine_stones":
                machine = state.machines.get(commitment.candidate.machine_id or "")
                if machine is None or machine.carried_stones <= 0:
                    self._drop_mission(hero_id)
            elif kind == "direct_chest":
                old = commitment.expected_chest
                destination = commitment.pending_chest_to
                if destination is not None:
                    if destination in state.chests:
                        commitment.expected_chest = destination
                        commitment.pending_chest_to = None
                    elif destination == commitment.candidate.bush and (old is None or old not in state.chests):
                        self._drop_mission(hero_id)
                        continue
                    elif old is not None and old in state.chests:
                        # The requested push did not happen; replan globally instead
                        # of following a suffix whose geometry is now wrong.
                        self._drop_mission(hero_id)
                        continue
                    else:
                        self._drop_mission(hero_id)
                        continue
                elif old is not None and old not in state.chests:
                    self._drop_mission(hero_id)
                    continue
                if hero_id in self._v14_missions and not commitment.actions:
                    self._drop_mission(hero_id)
            elif kind == "machine_chest":
                self._reconcile_machine_chest(state, hero_id, commitment)

    def _execute_simple(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> HeroAction | None:
        if not commitment.actions:
            self._drop_mission(hero_id)
            return None
        hero = state.heroes[hero_id]
        action = commitment.actions[0]
        if action in {HeroAction.UP, HeroAction.DOWN, HeroAction.LEFT, HeroAction.RIGHT}:
            move = Rules.hero_move(state, hero, action)
            if not move.valid:
                self._drop_mission(hero_id)
                return None
            if hero.stamina < move.stamina_cost:
                return HeroAction.WAIT
        elif action in PUSH_ACTIONS:
            push = Rules.chest_push(state, hero, action)
            if not push.valid or not Rules.hero_chest_push_safe_this_tick(state, push):
                self._drop_mission(hero_id)
                return None
            if hero.stamina < 5:
                return HeroAction.WAIT
            if commitment.candidate.kind == "direct_chest":
                commitment.expected_chest = push.chest_from
                commitment.pending_chest_to = push.chest_to
        commitment.actions.pop(0)
        return action

    def _forecast_intercept_action(self, state: GameState, hero_id: HeroId, machine_id: str) -> HeroAction | None:
        """Find a short reachable intercept when the machine's current cell is not.

        Heroes move twice as fast as machines.  A bounded WAIT forecast is enough
        to catch many elevation-driven cases where chasing the current cell would
        stall forever while the autonomous machine moves into a reachable sector.
        """
        simulation = deepcopy(state)
        sim = Simulator(simulation)
        seen: set[Position] = set()
        best: tuple[int, int, HeroAction] | None = None
        for tick in range(1, 11):
            if simulation.remaining_time <= 0:
                break
            try:
                sim.step({HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT})
            except RuntimeError:
                break
            machine = simulation.machines.get(machine_id)
            if machine is None or machine.position in seen:
                continue
            seen.add(machine.position)
            path = find_score_path(state, hero_id, machine.position, max_expansions=7_000)
            if path is None or not path.steps or path.ticks > tick + 2:
                continue
            rank = (tick, path.ticks, path.steps[0].action)
            if best is None or rank[:2] < best[:2]:
                best = rank
        return None if best is None else best[2]

    def _safe_release_rotation(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> HeroAction | None:
        """Turn a controlled machine away from the target chest before giving up.

        This prevents a failed micro-plan from immediately becoming an autonomous
        push that strands the chest on a non-bush boundary or cliff.
        """
        hero = state.heroes[hero_id]
        machine_id = commitment.candidate.machine_id
        if not hero.is_hacking or hero.hacking_machine_id != machine_id or hero.battery <= 0:
            return None
        machine = state.machines[machine_id]
        expected = commitment.expected_chest
        if expected is None or Rules.machine_forward(machine) != expected:
            return None
        from app.domain.enums import CLOCKWISE, COUNTER_CLOCKWISE, ORIENTATION_TO_DIRECTION
        options = [
            (HeroAction.HACK_CW, CLOCKWISE[machine.orientation]),
            (HeroAction.HACK_CCW, COUNTER_CLOCKWISE[machine.orientation]),
        ]
        ranked = []
        for action, orientation in options:
            direction = ORIENTATION_TO_DIRECTION[orientation]
            dr, dc = DIRECTION_VECTORS[direction]
            target = machine.position.moved(dr, dc)
            chest_penalty = 1000 if target in state.chests else 0
            terrain_penalty = 100 if not state.game_map.in_bounds(target) or target in state.game_map.rocks else 0
            ranked.append((chest_penalty + terrain_penalty, action))
        ranked.sort(key=lambda item: (item[0], item[1].value))
        commitment.release_after_rotation = True
        return ranked[0][1]

    def _machine_chase_action(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> HeroAction | None:
        candidate = commitment.candidate
        machine = state.machines.get(candidate.machine_id or "")
        if machine is None or (machine.is_hacked and machine.hacked_by != hero_id):
            self._drop_mission(hero_id)
            return None
        hero = state.heroes[hero_id]
        if hero.position == machine.position:
            if hero.battery <= 0:
                self._drop_mission(hero_id)
                return None
            return HeroAction.HACK

        path = find_score_path(state, hero_id, machine.position, max_expansions=12_000)
        if path is None or not path.steps:
            intercept = self._forecast_intercept_action(state, hero_id, machine.id)
            if intercept is not None:
                commitment.blocked_ticks = 0
                return intercept
            commitment.blocked_ticks += 1
            if commitment.blocked_ticks >= self.MAX_MACHINE_BLOCKED_TICKS:
                self._drop_mission(hero_id)
                return None
            return HeroAction.WAIT
        step = path.steps[0]
        if hero.stamina < step.stamina_cost:
            return HeroAction.WAIT
        commitment.blocked_ticks = 0
        return step.action

    def _refresh_machine_control_plan(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> bool:
        candidate = commitment.candidate
        machine_id = candidate.machine_id
        chest = commitment.expected_chest
        if machine_id is None or chest is None or candidate.bush is None:
            return False
        machine = state.machines[machine_id]
        plan: MachineChestPlan | None = plan_machine_chest_to_bush(
            state,
            machine,
            chest,
            candidate.bush,
            max_expansions=130 if state.game_map.height * state.game_map.width <= 400 else 75,
            reposition_expansions=3_200 if state.game_map.height * state.game_map.width <= 400 else 1_800,
        )
        if plan is None or plan.battery_cost > state.heroes[hero_id].battery:
            return False
        commitment.actions = list(plan.actions)
        commitment.replans += 1
        return True

    def _execute_machine_chest(self, state: GameState, hero_id: HeroId, commitment: MissionCommitment) -> HeroAction | None:
        candidate = commitment.candidate
        hero = state.heroes[hero_id]
        machine_id = candidate.machine_id
        if machine_id is None:
            self._drop_mission(hero_id)
            return None
        if commitment.release_after_rotation:
            self._drop_mission(hero_id)
            return None

        if hero.is_hacking and hero.hacking_machine_id != machine_id:
            self._drop_mission(hero_id)
            return None
        if not hero.is_hacking:
            return self._machine_chase_action(state, hero_id, commitment)

        machine = state.machines[machine_id]
        if not commitment.actions:
            if commitment.replans >= self.MAX_MACHINE_REPLANS:
                release = self._safe_release_rotation(state, hero_id, commitment)
                if release is not None:
                    return release
                self._drop_mission(hero_id)
                return None
            if not self._refresh_machine_control_plan(state, hero_id, commitment):
                commitment.blocked_ticks += 1
                if commitment.blocked_ticks >= self.MAX_MACHINE_BLOCKED_TICKS:
                    release = self._safe_release_rotation(state, hero_id, commitment)
                    if release is not None:
                        return release
                    self._drop_mission(hero_id)
                    return None
                return HeroAction.WAIT
            commitment.blocked_ticks = 0

        action = commitment.actions[0]
        if action == HeroAction.HACK_MOVE:
            if machine.pending_move:
                return HeroAction.WAIT
            if hero.battery <= 0:
                self._drop_mission(hero_id)
                return None
            if not Rules.machine_forward_queueable(state, machine):
                commitment.actions.clear()
                commitment.blocked_ticks += 1
                if commitment.blocked_ticks >= self.MAX_MACHINE_BLOCKED_TICKS:
                    release = self._safe_release_rotation(state, hero_id, commitment)
                    if release is not None:
                        return release
                    self._drop_mission(hero_id)
                    return None
                return HeroAction.WAIT
            front = Rules.machine_forward(machine)
            if commitment.expected_chest is not None and front == commitment.expected_chest:
                direction = ACTION_TO_DIRECTION[
                    {
                        "FACING_UP": HeroAction.UP,
                        "FACING_RIGHT": HeroAction.RIGHT,
                        "FACING_DOWN": HeroAction.DOWN,
                        "FACING_LEFT": HeroAction.LEFT,
                    }[machine.orientation.value]
                ]
                dr, dc = DIRECTION_VECTORS[direction]
                commitment.pending_chest_to = front.moved(dr, dc)
            commitment.actions.pop(0)
            return action

        if action in {HeroAction.HACK_CW, HeroAction.HACK_CCW}:
            if hero.battery <= 0:
                self._drop_mission(hero_id)
                return None
            commitment.actions.pop(0)
            return action
        if action == HeroAction.WAIT:
            commitment.actions.pop(0)
            return HeroAction.WAIT

        # Machine-chest planner currently emits only MOVE/WAIT/rotations.  Any
        # unexpected action is safer to replan than to guess.
        commitment.actions.clear()
        return HeroAction.WAIT

    def _execute_commitment(self, state: GameState, hero_id: HeroId) -> HeroAction | None:
        commitment = self._v14_missions.get(hero_id)
        if commitment is None:
            return None
        if commitment.candidate.kind == "machine_chest":
            return self._execute_machine_chest(state, hero_id, commitment)
        return self._execute_simple(state, hero_id, commitment)

    # ------------------------------------------------------------------
    # Strategy protocol
    # ------------------------------------------------------------------

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished or state.remaining_time <= 0:
            return True
        if self._v14_missions:
            return False
        # Do not stop merely because the instantaneous score peaked while a
        # potentially +150 chest still exists.  The inherited strategy gets the
        # final say only after V14 has repeatedly failed to create a mission.
        if state.chests and self._v14_no_mission_ticks < 8:
            return False
        return super().should_end(state)

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        self._reconcile(state)

        # Critical V10/V13 chest defense remains higher priority than normal
        # missions.  Commitments survive and are revalidated on the next tick.
        defense = self._active_defense_short_circuit(state)
        if defense is not None:
            return defense

        self._assign_free_heroes(state)
        if not self._v14_missions:
            self._v14_no_mission_ticks += 1
            return super().next_actions(state)

        decisions: dict[HeroId, HeroAction] = {}
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            action = self._execute_commitment(state, hero_id)
            decisions[hero_id] = action if action is not None else HeroAction.WAIT
            if hero_id in self._v14_missions:
                self.last_decisions[hero_id.value] = self._v14_missions[hero_id].candidate.description
            else:
                self.last_decisions[hero_id.value] = "attendre/replanifier"

        if all(action == HeroAction.WAIT for action in decisions.values()):
            self._v14_no_mission_ticks += 1
        else:
            self._v14_no_mission_ticks = 0
        return decisions
