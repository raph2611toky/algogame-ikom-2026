from __future__ import annotations

"""Predictive/global strategy layer for AlgoGames 2.

V13 deliberately builds on V12 instead of rewriting proven mechanics.  The
simulator/rules remain the only source of truth.  This layer improves *choice*:
score-aware direct routing, elevation-aware task valuation, predictive machine
hazard simulation, and activation of the V10/V11/V12 orchestration on the small
hidden-map sizes where older versions intentionally fell back to V9.
"""

from copy import deepcopy
from dataclasses import dataclass

from app.domain.enums import MOVE_ACTIONS, PUSH_ACTIONS, HeroAction, HeroId, MachineKind
from app.domain.models import GameState, Position
from app.engine.machine_planner import plan_machine_to_obstacle
from app.engine.pathfinding import hero_neighbors
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.score_pathfinding import find_score_path, score_cost_units
from app.engine.simulator import Simulator
from app.engine.rules import Rules
from app.engine.strategy_v4 import DirectChestPlan, MachineTask
from app.engine.strategy_v9 import StrategicRelayPortfolioStrategy
from app.engine.strategy_v10 import _MachineHazard
from app.engine.strategy_v12 import AddendumAwareParallelPortfolioStrategy


@dataclass(frozen=True, slots=True)
class _TaskEstimate:
    score_units: int
    ticks: int
    battery: int
    machine_id: str
    structurally_blocked: bool = False


class PredictiveGlobalPortfolioStrategy(AddendumAwareParallelPortfolioStrategy):
    """V13: global score/elevation reasoning over the proven V12 mechanics.

    Main changes are intentionally meta-level:

    * direct chest choices minimize the actual score loss (time + stamina), not
      elapsed ticks first;
    * machine-obstacle estimates use real hero/machine planners, so elevation,
      directed reachability, rotations, look-ahead and battery are reflected;
    * target-chest ordering evaluates the complete unlock -> direct-push chain
      and the value of shared obstacles;
    * autonomous hazards are forecast with the production Simulator, allowing
      other machines to move during the forecast instead of freezing them;
    * V10/V11/V12 protections are enabled on <=160-cell maps too.  V10 kept a
      V9-only compatibility shortcut there; the hidden evaluation size is exactly
      where we want the newer official Addendum reasoning to be active.

    Existing route commitment, relay stamina, machine micro-plans, look-ahead,
    joint deadlock escape, and all low-level rules are inherited unchanged.
    """

    CHEST_REWARD_UNITS = 600      # 150 score * 4
    STONE_REWARD_UNITS = 100      # 25 score * 4
    SHARED_OBSTACLE_BONUS = 70
    STRUCTURAL_MACHINE_PENALTY = 60
    TEMPORAL_MACHINE_RISK_PENALTY = 90
    MAX_GLOBAL_OBSTACLES = 10
    PREDICTIVE_HAZARD_HORIZON = 32

    def __init__(self, *, planning_bias: str = "score", **kwargs) -> None:
        super().__init__(**kwargs)
        if planning_bias not in {"score", "balanced", "time"}:
            raise ValueError(f"planning_bias inconnu: {planning_bias}")
        self.planning_bias = planning_bias
        self._v13_target_signature: tuple[object, ...] | None = None
        self._v13_machine_estimate_cache: dict[tuple[object, ...], _TaskEstimate | None] = {}

    # ------------------------------------------------------------------
    # 1) Direct chest routing: optimize the official score, not ticks first.
    # ------------------------------------------------------------------

    def _direct_chest_plans(self, state: GameState, *, only_chest: Position | None = None) -> list[DirectChestPlan]:
        """V8 planner budget + V13 strict immediate machine occupancy guard.

        The shared chest planner keeps legacy behavior by default because a machine
        that occupies a future PUSH destination can move away before that PUSH. V13
        asks for conservative immediate plans; the portfolio still keeps V12/V10/V8
        candidates, so this extra safety cannot erase a proven older trajectory.
        """
        if not state.chests or not state.game_map.bushes:
            return []
        chests = [only_chest] if only_chest is not None and only_chest in state.chests else sorted(state.chests)
        cells = state.game_map.height * state.game_map.width
        if cells <= 160:
            max_expansions = max(6000, min(70000, cells * 350))
            budget = self.max_chest_pairs_per_hero * 2
            bush_limit = len(state.game_map.bushes)
        elif cells <= 400:
            max_expansions = 9000
            budget = min(self.max_chest_pairs_per_hero * 2, max(8, len(chests) * 4))
            bush_limit = 2
        elif cells <= 800:
            max_expansions = 7000
            budget = min(self.max_chest_pairs_per_hero * 2, max(6, len(chests) * 3))
            bush_limit = 2
        else:
            max_expansions = 5000
            budget = min(self.max_chest_pairs_per_hero * 2, max(4, len(chests) * 2))
            bush_limit = 1

        plans: list[DirectChestPlan] = []
        attempts = 0
        for chest in chests:
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                hero = state.heroes[hero_id]
                bushes = sorted(
                    state.game_map.bushes,
                    key=lambda bush: (
                        chest.manhattan(bush),
                        hero.position.manhattan(chest),
                        bush.row,
                        bush.col,
                    ),
                )[:bush_limit]
                for bush in bushes:
                    if attempts >= budget:
                        break
                    attempts += 1
                    plan = plan_chest_to_bush(
                        state,
                        hero_id,
                        chest,
                        bush,
                        max_expansions=max_expansions,
                        optimize_for_score=True,
                        avoid_machine_push_destinations=True,
                    )
                    if plan is not None and plan.actions:
                        plans.append(DirectChestPlan(hero_id, chest, bush, plan))
        plans.sort(key=lambda item: item.cost_key)
        return plans

    @staticmethod
    def _recovery_cost(stamina_needed: int, stamina_available: int) -> tuple[int, int, int]:
        """Return (wait_ticks, recovered_stamina, net_score_units).

        WAIT costs two quarter-score units per tick through remaining time, while
        every two WAIT ticks recover one stamina quarter-score unit.  Hence one
        recovered stamina usually costs 3 units net, not 4.
        """
        deficit = max(0, stamina_needed - stamina_available)
        ticks = deficit * 2
        recovered = deficit
        return ticks, recovered, max(0, score_cost_units(ticks, 0) - recovered)

    def _plan_runtime_key(self, state: GameState, plan: DirectChestPlan) -> tuple[object, ...]:
        hero = state.heroes[plan.hero_id]
        recovery_ticks, _recovered, recovery_units = self._recovery_cost(
            plan.plan.stamina_cost,
            hero.stamina,
        )
        effective_ticks = plan.plan.ticks + recovery_ticks
        effective_units = plan.plan.score_cost_units + recovery_units

        if self.planning_bias == "time":
            return (
                effective_ticks,
                effective_units,
                recovery_ticks,
                plan.plan.stamina_cost,
                plan.chest.row,
                plan.chest.col,
                plan.hero_id.value,
            )
        if self.planning_bias == "balanced":
            # One extra tick is two units.  Balanced keeps score primary but uses
            # effective runtime early enough to avoid very slow equivalent routes.
            return (
                effective_units,
                effective_ticks,
                recovery_ticks,
                plan.plan.stamina_cost,
                plan.chest.row,
                plan.chest.col,
                plan.hero_id.value,
            )
        return (
            effective_units,
            recovery_ticks,
            effective_ticks,
            plan.plan.stamina_cost,
            plan.chest.row,
            plan.chest.col,
            plan.hero_id.value,
        )

    def _choose_direct_pair(
        self,
        state: GameState,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> tuple[DirectChestPlan, DirectChestPlan] | None:
        f_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IKOTOFOSA]
        m_plans = [p for (hid, _), p in plans.items() if hid == HeroId.IMAHAKI]
        best: tuple[tuple[object, ...], tuple[DirectChestPlan, DirectChestPlan]] | None = None
        for f_plan in f_plans:
            for m_plan in m_plans:
                if f_plan.chest == m_plan.chest:
                    continue
                f_wait, f_rec, _ = self._recovery_cost(
                    f_plan.plan.stamina_cost, state.heroes[HeroId.IKOTOFOSA].stamina
                )
                m_wait, m_rec, _ = self._recovery_cost(
                    m_plan.plan.stamina_cost, state.heroes[HeroId.IMAHAKI].stamina
                )
                f_ticks = f_plan.plan.ticks + f_wait
                m_ticks = m_plan.plan.ticks + m_wait
                # Parallel wall-clock time is max(), while both stamina resources
                # contribute to the final score. Recovered WAIT stamina is credited.
                parallel_units = (
                    2 * max(f_ticks, m_ticks)
                    + f_plan.plan.stamina_cost
                    + m_plan.plan.stamina_cost
                    - f_rec
                    - m_rec
                )
                if self.planning_bias == "time":
                    rank = (
                        max(f_ticks, m_ticks),
                        parallel_units,
                        f_ticks + m_ticks,
                        f_plan.chest.row,
                        f_plan.chest.col,
                        m_plan.chest.row,
                        m_plan.chest.col,
                    )
                else:
                    rank = (
                        parallel_units,
                        max(f_ticks, m_ticks),
                        f_ticks + m_ticks,
                        f_wait + m_wait,
                        f_plan.chest.row,
                        f_plan.chest.col,
                        m_plan.chest.row,
                        m_plan.chest.col,
                    )
                if best is None or rank < best[0]:
                    best = (rank, (f_plan, m_plan))
        if best is None:
            return None

        f_plan, m_plan = best[1]
        f_wait, _, _ = self._recovery_cost(
            f_plan.plan.stamina_cost, state.heroes[HeroId.IKOTOFOSA].stamina
        )
        m_wait, _, _ = self._recovery_cost(
            m_plan.plan.stamina_cost, state.heroes[HeroId.IMAHAKI].stamina
        )
        # Keep V8's safety intent, but permit a little more recovery when the
        # score-aware pair is still globally cheaper than serial execution.
        if max(f_wait, m_wait) > 28:
            return None
        return best[1]

    # ------------------------------------------------------------------
    # 2) Elevation-aware machine task valuation (no Manhattan fiction).
    # ------------------------------------------------------------------

    def _operational_signature(self, state: GameState) -> tuple[object, ...]:
        return (
            self._topology_signature(state),
            tuple(
                (hid.value, h.position.row, h.position.col, h.stamina, h.battery, h.hacking_machine_id)
                for hid, h in sorted(state.heroes.items(), key=lambda item: item[0].value)
            ),
            tuple(
                sorted(
                    (
                        m.id,
                        m.position.row,
                        m.position.col,
                        m.orientation.value,
                        m.hacked_by.value if m.hacked_by else None,
                        m.pending_move,
                        m.auto_move_pending,
                        m.steps_since_dig,
                    )
                    for m in state.machines.values()
                )
            ),
        )

    def _control_plan_temporally_safe(
        self,
        state: GameState,
        hero_id: HeroId,
        machine_id: str,
        control,
    ) -> bool:
        """Replay a short hacked-machine micro-plan with all machines moving.

        The static machine planner necessarily sees the other machines at their
        current cells.  The official Addendum rechecks Look Ahead on the second
        tick of HACK_MOVE, so another autonomous machine can enter the scan area
        after the plan was created.  This bounded rollout uses the production
        Simulator to detect that case before giving the task a high global rank.
        """
        hero = state.heroes[hero_id]
        if not hero.is_hacking or hero.hacking_machine_id != machine_id:
            return True
        simulation = deepcopy(state)
        sim = Simulator(simulation)
        other_id = self._other(hero_id)
        actions = list(control.actions[:24])
        for action in actions:
            if simulation.remaining_time <= 0:
                return False
            before = simulation.machines[machine_id].position
            try:
                rec = sim.step({hero_id: action, other_id: HeroAction.WAIT})
            except RuntimeError:
                return False
            effective = rec.effective_actions[hero_id]
            if action == HeroAction.HACK_MOVE and effective != HeroAction.HACK_MOVE:
                return False
            # For the explicit WAIT after HACK_MOVE, the machine must either have
            # completed the queued move or still be in a legitimate pending state.
            # If Look Ahead cancelled it, pending_move is cleared and the position
            # stays unchanged: flag the plan as temporally risky.
            machine = simulation.machines[machine_id]
            if action == HeroAction.WAIT and before == machine.position and not machine.pending_move:
                previous = rec.requested_actions.get(hero_id)
                if previous == HeroAction.WAIT and any(
                    event.type == 'MACHINE_MOVE_BLOCKED' and event.actor == machine_id
                    for event in rec.events
                ):
                    return False
        return True

    def _estimate_single_machine_task(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacle: Position,
    ) -> _TaskEstimate | None:
        cache_key = (self._operational_signature(state), hero_id.value, obstacle.row, obstacle.col)
        if cache_key in self._v13_machine_estimate_cache:
            return self._v13_machine_estimate_cache[cache_key]

        hero = state.heroes[hero_id]
        if hero.battery <= 0:
            self._v13_machine_estimate_cache[cache_key] = None
            return None
        kind = MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        candidates: list[_TaskEstimate] = []

        for machine in sorted(state.machines.values(), key=lambda item: item.id):
            if machine.kind != kind:
                continue
            if machine.is_hacked and machine.hacked_by != hero_id:
                continue
            if hero.is_hacking and hero.hacking_machine_id != machine.id:
                continue

            structural = False
            control = plan_machine_to_obstacle(
                state,
                machine,
                obstacle,
                max_expansions=20_000,
                ignore_other_machines=False,
            )
            if control is None:
                # A current X/G look-ahead stand-off may be temporary.  A structural
                # retry tells global ranking that the task exists but charges a risk
                # penalty; runtime V12 still has to resolve the real collision.
                control = plan_machine_to_obstacle(
                    state,
                    machine,
                    obstacle,
                    max_expansions=20_000,
                    ignore_other_machines=True,
                )
                structural = control is not None
            if control is None:
                continue

            if hero.is_hacking:
                approach_ticks = 0
                approach_stamina = 0
                hack_ticks = 0
                hack_battery = 0
            else:
                approach = find_score_path(state, hero_id, machine.position, max_expansions=30_000)
                if approach is None:
                    continue
                approach_ticks = approach.ticks
                approach_stamina = approach.total_stamina_cost
                hack_ticks = 1
                hack_battery = 1

            battery = control.battery_cost + hack_battery
            if battery > hero.battery:
                continue

            wait_ticks, wait_recovered, wait_units = self._recovery_cost(approach_stamina, hero.stamina)
            stamina_after_approach = min(100, hero.stamina + wait_recovered) - approach_stamina
            hacking_ticks = hack_ticks + control.ticks
            hacking_recovered = min(max(0, 100 - stamina_after_approach), hacking_ticks // 2)
            total_ticks = wait_ticks + approach_ticks + hacking_ticks
            if total_ticks > state.remaining_time:
                continue
            temporal_risk = (
                hero.is_hacking
                and not self._control_plan_temporally_safe(state, hero_id, machine.id, control)
            )
            units = (
                score_cost_units(approach_ticks + hacking_ticks, approach_stamina, battery)
                + wait_units
                - hacking_recovered
                + (self.STRUCTURAL_MACHINE_PENALTY if structural else 0)
                + (self.TEMPORAL_MACHINE_RISK_PENALTY if temporal_risk else 0)
            )
            candidates.append(
                _TaskEstimate(
                    score_units=max(0, units),
                    ticks=total_ticks,
                    battery=battery,
                    machine_id=machine.id,
                    structurally_blocked=structural,
                )
            )

        result = min(
            candidates,
            key=lambda item: (item.score_units, item.ticks, item.structurally_blocked, item.machine_id),
            default=None,
        )
        self._v13_machine_estimate_cache[cache_key] = result
        if len(self._v13_machine_estimate_cache) > 768:
            self._v13_machine_estimate_cache.clear()
            self._v13_machine_estimate_cache[cache_key] = result
        return result

    def _machine_cost_estimate(self, state: GameState, hero_id: HeroId, obstacles: set[Position]) -> int:
        if not obstacles:
            return 0
        estimates: list[_TaskEstimate] = []
        ordered = sorted(
            obstacles,
            key=lambda p: (-self._obstacle_support_cache.get(p, 1), p.row, p.col),
        )[: self.MAX_GLOBAL_OBSTACLES]
        for obstacle in ordered:
            estimate = self._estimate_single_machine_task(state, hero_id, obstacle)
            if estimate is None:
                return 100_000
            estimates.append(estimate)
        # Independent estimates intentionally over-count repeated approach/HACK a
        # little; that is safer than Manhattan under-counting an elevation detour.
        return sum(item.score_units for item in estimates)

    def _machine_tasks_for(
        self,
        state: GameState,
        hero_id: HeroId,
        obstacles,
        *,
        ignore_other_machines: bool = False,
    ) -> list[MachineTask]:
        obstacle_list = list(obstacles)
        if len(obstacle_list) > self.MAX_GLOBAL_OBSTACLES:
            scored = []
            for obstacle in obstacle_list:
                estimate = self._estimate_single_machine_task(state, hero_id, obstacle)
                score = 100_000 if estimate is None else estimate.score_units
                scored.append(
                    (
                        -self._obstacle_support_cache.get(obstacle, 1),
                        score,
                        obstacle.row,
                        obstacle.col,
                        obstacle,
                    )
                )
            scored.sort()
            obstacle_list = [row[-1] for row in scored[: self.MAX_GLOBAL_OBSTACLES]]

        # Explicitly bypass V10's Manhattan pre-selection.  V9 inherits V8's task
        # builder; on the evaluation-size maps it evaluates every supplied obstacle
        # with find_score_path + machine planner.
        tasks = StrategicRelayPortfolioStrategy._machine_tasks_for(
            self,
            state,
            hero_id,
            obstacle_list,
            ignore_other_machines=ignore_other_machines,
        )
        tasks.sort(
            key=lambda task: (
                -self._obstacle_support_cache.get(task.obstacle, 1),
                task.total_cost_units,
                task.total_ticks,
                0 if state.heroes[hero_id].hacking_machine_id == task.machine_id else 1,
                task.obstacle.row,
                task.obstacle.col,
                task.machine_id,
            )
        )
        return tasks

    # ------------------------------------------------------------------
    # 3) Global target valuation: unlock + route + resources + shared progress.
    # ------------------------------------------------------------------

    @staticmethod
    def _route_stone_bonus(state: GameState, plan: DirectChestPlan) -> int:
        hero_pos = state.heroes[plan.hero_id].position
        chest_pos = plan.chest
        collected: set[Position] = set()
        for action in plan.plan.actions:
            if action in MOVE_ACTIONS:
                step = next(
                    (candidate for candidate in hero_neighbors(state, plan.hero_id, hero_pos) if candidate.action == action),
                    None,
                )
                if step is None:
                    continue
                hero_pos = step.destination
                if hero_pos in state.stones:
                    collected.add(hero_pos)
            elif action in PUSH_ACTIONS:
                # A successful PUSH moves the hero onto the chest's former cell.
                dr, dc = Rules.direction_delta(action)
                hero_pos = chest_pos
                chest_pos = chest_pos.moved(dr, dc)
                if hero_pos in state.stones:
                    collected.add(hero_pos)
        return len(collected) * PredictiveGlobalPortfolioStrategy.STONE_REWARD_UNITS

    def _post_unlock_plan(
        self,
        state: GameState,
        chest: Position,
        holes: set[Position],
        trees: set[Position],
    ) -> DirectChestPlan | None:
        hypothetical = self._copy_without(state, holes, trees)
        plans = self._direct_chest_plans(hypothetical, only_chest=chest)
        if not plans:
            return None
        return min(plans, key=lambda item: self._plan_runtime_key(hypothetical, item))

    def _global_chest_rank(self, state: GameState, chest: Position, profiles) -> tuple[object, ...]:
        profile = profiles[chest]
        holes, trees = self._current_obstacle_sets(state, profile)
        if holes or trees:
            # Include bounded cross-role prerequisites already known by V10.
            holes, trees = self._expanded_unlock_obstacles(state, profile)
            holes = set(holes) & set(state.holes)
            trees = set(trees) & set(state.trees)

        unlock_units = (
            self._machine_cost_estimate(state, HeroId.IKOTOFOSA, holes)
            + self._machine_cost_estimate(state, HeroId.IMAHAKI, trees)
        )
        if unlock_units >= 100_000:
            return (1, 10**9, 10**9, 10**9, chest.row, chest.col)

        direct = self._post_unlock_plan(state, chest, holes, trees)
        if direct is None:
            return (1, 10**9, 10**9, 10**9, chest.row, chest.col)

        direct_key = self._plan_runtime_key(self._copy_without(state, holes, trees), direct)
        direct_units = int(direct_key[0]) if self.planning_bias != "time" else int(direct_key[1])
        if self.planning_bias == "score":
            direct_ticks = int(direct_key[2])
        elif self.planning_bias == "balanced":
            direct_ticks = int(direct_key[1])
        else:
            direct_ticks = int(direct_key[0])
        shared_bonus = sum(
            max(0, self._obstacle_support_cache.get(obstacle, 1) - 1) * self.SHARED_OBSTACLE_BONUS
            for obstacle in (holes | trees)
        )
        stone_bonus = self._route_stone_bonus(self._copy_without(state, holes, trees), direct)

        # If an autonomous machine already threatens this specific chest, saving it
        # sooner has real expected value.  Defense logic still remains authoritative.
        urgency_bonus = 0
        for machine in state.machines.values():
            if machine.is_hacked:
                continue
            hazard = self._predict_autonomous_hazard(state, machine.id, horizon=12)
            if hazard is not None and hazard.chest_from == chest:
                urgency_bonus = max(urgency_bonus, 180 if hazard.risk >= self.AUTONOMOUS_HAZARD_CRITICAL else 80)

        total_cost = unlock_units + direct_units
        utility = self.CHEST_REWARD_UNITS + shared_bonus + stone_bonus + urgency_bonus - total_cost
        if self.planning_bias == "time":
            return (
                0,
                len(holes) + len(trees),
                direct_ticks,
                -utility,
                total_cost,
                chest.row,
                chest.col,
            )
        return (
            0,
            -utility,
            total_cost,
            len(holes) + len(trees),
            direct_ticks,
            chest.row,
            chest.col,
        )

    def _select_target_chest(self, state: GameState) -> Position | None:
        self._refresh_impossible(state)
        signature = self._topology_signature(state)
        if (
            self._v13_target_signature == signature
            and self._target_chest in state.chests
            and self._target_chest not in self._impossible_chests
        ):
            return self._target_chest

        profiles = self._viable_profiles(state)
        if not profiles:
            self._target_chest = None
            self._v13_target_signature = signature
            return None
        self._refresh_opportunity_cache(state)
        candidates = [(self._global_chest_rank(state, chest, profiles), chest) for chest in profiles]
        candidates.sort(key=lambda item: item[0])
        self._target_chest = candidates[0][1] if candidates else None
        self._opportunity_target = self._target_chest
        self._v13_target_signature = signature
        return self._target_chest

    # ------------------------------------------------------------------
    # 4) Temporal autonomous forecast using the exact production Simulator.
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_forecast_cell(state: GameState, machine_pos: Position) -> Position:
        candidates = [
            p
            for p in state.game_map.all_positions()
            if (
                p not in state.game_map.rocks
                and p not in state.trees
                and p not in state.holes
                and p not in state.chests
            )
        ]
        if not candidates:
            return machine_pos
        anchors = [machine_pos, *state.chests, *(m.position for m in state.machines.values())]
        return max(
            candidates,
            key=lambda p: (
                min((p.manhattan(a) for a in anchors), default=0),
                p.row,
                p.col,
            ),
        )

    def _predict_autonomous_hazard(
        self,
        state: GameState,
        machine_id: str,
        *,
        orientation=None,
        horizon: int | None = None,
    ) -> _MachineHazard | None:
        machine_real = state.machines.get(machine_id)
        if machine_real is None:
            return None
        horizon = min(int(horizon or self.PREDICTIVE_HAZARD_HORIZON), 48)
        signature = ("v13-temporal", self._hazard_signature(state, machine_id, orientation), horizon)
        if signature in self._hazard_cache:
            return self._hazard_cache[signature]

        simulation = deepcopy(state)
        machine = simulation.machines[machine_id]
        if orientation is not None:
            machine.orientation = orientation

        # Forecast the requested release.  Other hacked machines stay held, while
        # autonomous machines continue moving in the real Simulator and therefore
        # change future look-ahead occupancy over time.
        controller = machine.hacked_by
        machine.hacked_by = None
        machine.pending_move = False
        machine.auto_move_pending = False
        machine.resume_delay = 0
        if controller is not None:
            hero = simulation.heroes[controller]
            hero.hacking_machine_id = None
            hero.position = self._safe_forecast_cell(simulation, machine.position)
        for hero_id, hero in simulation.heroes.items():
            if hero.hacking_machine_id is None and hero_id != controller:
                hero.position = self._safe_forecast_cell(simulation, machine.position)

        sim = Simulator(simulation)
        trace: list[Position] = [machine.position]
        result: _MachineHazard | None = None

        for index in range(1, horizon + 1):
            if simulation.elapsed >= simulation.game_map.time_limit:
                break
            try:
                record = sim.step(
                    {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
                )
            except RuntimeError:
                break
            trace.append(simulation.machines[machine_id].position)
            for event in record.events:
                if event.actor != machine_id:
                    continue
                chest_to = event.position
                chest_from = simulation.machines[machine_id].position if chest_to is not None else None
                if event.type == "CHEST_DESTROYED_CLIFF":
                    result = _MachineHazard(
                        machine_id, 120_000, index, chest_from, chest_to,
                        "coffre detruit par falaise >=5 niveaux",
                        tuple(dict.fromkeys(reversed(trace[-12:]))),
                    )
                    break
                if event.type == "CHEST_LOST":
                    result = _MachineHazard(
                        machine_id, 100_000, index, chest_from, chest_to,
                        "coffre pousse dans un trou",
                        tuple(dict.fromkeys(reversed(trace[-12:]))),
                    )
                    break
                if event.type == "CHEST_PUSHED" and chest_to is not None:
                    if self._is_non_bush_boundary(simulation, chest_to):
                        result = _MachineHazard(
                            machine_id, 90_000, index, chest_from, chest_to,
                            "coffre pousse vers un bord non recuperable",
                            tuple(dict.fromkeys(reversed(trace[-12:]))),
                        )
                        break
                    before = min((chest_from.manhattan(b) for b in simulation.game_map.bushes), default=0) if chest_from else 0
                    after = min((chest_to.manhattan(b) for b in simulation.game_map.bushes), default=0)
                    if after >= before + 4:
                        result = _MachineHazard(
                            machine_id, 25_000, index, chest_from, chest_to,
                            "coffre fortement eloigne d'une cachette",
                            tuple(dict.fromkeys(reversed(trace[-12:]))),
                        )
                        break
            if result is not None:
                break

        self._hazard_cache[signature] = result
        if len(self._hazard_cache) > 512:
            self._hazard_cache.clear()
            self._hazard_cache[signature] = result
        return result

    # ------------------------------------------------------------------
    # 5) Run the enhanced orchestration on evaluation-sized maps as well.
    # ------------------------------------------------------------------

    def should_end(self, state: GameState) -> bool:
        # Completed objectives and the time limit always dominate stale internal
        # commitments. Keeping a machine micro-plan alive after the last chest/stone
        # only burns score and made some otherwise solved maps run to TIME_LIMIT.
        if state.objectives_finished or state.remaining_time <= 0:
            return True
        if self._joint_escape is not None or self._machine_commitments:
            return False
        # Bypass V10's <=160 V9-reference shortcut while retaining the exact
        # inherited stopping logic and all V13 overrides through dynamic dispatch.
        return StrategicRelayPortfolioStrategy.should_end(self, state)

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        defense = self._active_defense_short_circuit(state)
        if defense is not None:
            self._rotation_guard(state, defense)
            self._deadlock_resolver(state, defense)
            return defense

        # Same V10 production pipeline, but without its <=160 early return to the
        # separate V9 object. Calling V9's inherited core on `self` still dispatches
        # to V10/V11/V12/V13 overrides for target selection, support and machines.
        decisions = StrategicRelayPortfolioStrategy.next_actions(self, state)
        self._protect_chests_from_autonomous_machines(state, decisions)
        self._rotation_guard(state, decisions)
        self._deadlock_resolver(state, decisions)
        return decisions
