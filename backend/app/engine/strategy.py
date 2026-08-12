from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from app.domain.enums import (
    CLOCKWISE,
    COUNTER_CLOCKWISE,
    DIRECTION_TO_ORIENTATION,
    DIRECTION_VECTORS,
    ORIENTATION_TO_DIRECTION,
    Direction,
    HeroAction,
    HeroId,
    MachineKind,
    Orientation,
    PUSH_ACTIONS,
)
from app.domain.models import GameState, MachineState, Position
from app.engine.chest_planner import plan_chest_to_bush
from app.engine.machine_pathfinding import direction_between, find_machine_path
from app.engine.pathfinding import PathStep, find_path, hero_neighbors
from app.engine.rules import Rules


@dataclass(frozen=True, slots=True)
class Candidate:
    action: HeroAction
    utility: float
    target_key: tuple[object, ...] | None
    description: str
    required_stamina: int = 0


class HeuristicStrategy:
    """Deterministic score-aware baseline AI.

    It combines:
    - A* hero pathfinding for stones and compatible machines;
    - A* / Sokoban-like search in (hero_position, chest_position) space for chests;
    - greedy compatible-machine control to open paths (F->Excavator holes,
      M->Grappler trees);
    - two-agent assignment that avoids giving both heroes the same immediate goal.

    This is intentionally a strong *baseline*, not the final competition optimizer.
    The architecture lets you replace this class later without touching the rules,
    API contract, replay, or actions.txt writer.
    """

    def __init__(
        self,
        *,
        max_stones_per_hero: int = 8,
        max_chest_pairs_per_hero: int = 6,
        stuck_end_threshold: int = 8,
    ) -> None:
        self.max_stones_per_hero = max_stones_per_hero
        self.max_chest_pairs_per_hero = max_chest_pairs_per_hero
        self.stuck_end_threshold = stuck_end_threshold
        self.stuck_ticks = 0
        self.last_decisions: dict[str, str] = {}

    def should_end(self, state: GameState) -> bool:
        if state.objectives_finished:
            return True
        if state.remaining_time <= 0:
            return True
        return self.stuck_ticks >= self.stuck_end_threshold

    @staticmethod
    def _utility(reward: int, ticks: int, stamina_cost: int, battery_cost: int = 0) -> float:
        # Mirrors the official score opportunity costs approximately:
        # T contributes 1/2 point per remaining tick, resources contribute 1/4.
        return reward - (0.5 * ticks) - (0.25 * stamina_cost) - (0.25 * battery_cost)

    def _stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        hero = state.heroes[hero_id]
        stones = sorted(state.stones, key=lambda p: (hero.position.manhattan(p), p.row, p.col))
        candidates: list[Candidate] = []
        for stone in stones[: self.max_stones_per_hero]:
            path = find_path(state, hero_id, stone)
            if not path or not path.steps:
                continue
            first = path.steps[0]
            if path.ticks > state.remaining_time:
                continue
            candidates.append(
                Candidate(
                    action=first.action,
                    utility=self._utility(25, path.ticks, path.total_stamina_cost),
                    target_key=("stone", stone.row, stone.col),
                    description=f"pierre ({stone.row},{stone.col}) via A*",
                    required_stamina=first.stamina_cost,
                )
            )
        return candidates

    def _chest_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        hero = state.heroes[hero_id]
        if not state.chests or not state.game_map.bushes:
            return []
        pairs: list[tuple[int, Position, Position]] = []
        for chest in state.chests:
            for bush in state.game_map.bushes:
                rough = hero.position.manhattan(chest) + chest.manhattan(bush)
                pairs.append((rough, chest, bush))
        pairs.sort(key=lambda item: (item[0], item[1].row, item[1].col, item[2].row, item[2].col))

        candidates: list[Candidate] = []
        for _rough, chest, bush in pairs[: self.max_chest_pairs_per_hero]:
            plan = plan_chest_to_bush(state, hero_id, chest, bush)
            if not plan or not plan.actions or plan.ticks > state.remaining_time:
                continue
            first = plan.actions[0]
            if first in PUSH_ACTIONS:
                required = 5
            else:
                move = Rules.hero_move(state, hero, first)
                required = move.stamina_cost if move.valid else 1000
            candidates.append(
                Candidate(
                    action=first,
                    utility=self._utility(150, plan.ticks, plan.stamina_cost),
                    target_key=("chest", chest.row, chest.col),
                    description=(
                        f"coffre ({chest.row},{chest.col}) -> cachette "
                        f"({bush.row},{bush.col})"
                    ),
                    required_stamina=required,
                )
            )
        return candidates

    def _machine_stone_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        hero = state.heroes[hero_id]
        candidates: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.carried_stones <= 0:
                continue
            path = find_path(state, hero_id, machine.position)
            if not path or not path.steps:
                continue
            first = path.steps[0]
            reward = machine.carried_stones * 25
            candidates.append(
                Candidate(
                    action=first.action,
                    utility=self._utility(reward, path.ticks, path.total_stamina_cost),
                    target_key=("machine_stones", machine.id),
                    description=f"récupérer {machine.carried_stones} pierre(s) sur {machine.id}",
                    required_stamina=first.stamina_cost,
                )
            )
        return candidates

    def _compatible_machine_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        hero = state.heroes[hero_id]
        desired_kind = (
            MachineKind.EXCAVATOR if hero_id == HeroId.IKOTOFOSA else MachineKind.GRAPPLER
        )
        relevant_obstacles = state.holes if hero_id == HeroId.IKOTOFOSA else state.trees
        if not relevant_obstacles or hero.battery <= 0:
            return []

        candidates: list[Candidate] = []
        for machine in sorted(state.machines.values(), key=lambda m: m.id):
            if machine.kind != desired_kind or machine.is_hacked:
                continue
            if machine.position == hero.position:
                candidates.append(
                    Candidate(
                        action=HeroAction.HACK,
                        utility=4.0,
                        target_key=("machine", machine.id),
                        description=f"prendre contrôle de {machine.id}",
                        required_stamina=0,
                    )
                )
                continue
            path = find_path(state, hero_id, machine.position)
            if not path or not path.steps:
                continue
            first = path.steps[0]
            candidates.append(
                Candidate(
                    action=first.action,
                    utility=max(0.5, 4.0 - 0.25 * path.ticks),
                    target_key=("machine", machine.id),
                    description=f"rejoindre {machine.id}",
                    required_stamina=first.stamina_cost,
                )
            )
        return candidates

    @staticmethod
    def _rotation_action(current: Orientation, desired: Direction) -> HeroAction:
        target = DIRECTION_TO_ORIENTATION[desired]
        if current == target:
            return HeroAction.HACK_MOVE
        # At most two rotations. On a 180° tie, CW is deterministic.
        cw = current
        ccw = current
        for distance in range(1, 4):
            cw = CLOCKWISE[cw]
            if cw == target:
                cw_distance = distance
                break
        else:
            cw_distance = 4
        for distance in range(1, 4):
            ccw = COUNTER_CLOCKWISE[ccw]
            if ccw == target:
                ccw_distance = distance
                break
        else:
            ccw_distance = 4
        return HeroAction.HACK_CW if cw_distance <= ccw_distance else HeroAction.HACK_CCW

    def _exit_machine(self, state: GameState, hero_id: HeroId) -> HeroAction:
        hero = state.heroes[hero_id]
        for step in hero_neighbors(state, hero_id, hero.position):
            if hero.stamina >= step.stamina_cost:
                return step.action
        return HeroAction.WAIT

    def _control_machine(self, state: GameState, hero_id: HeroId) -> Candidate:
        hero = state.heroes[hero_id]
        machine = state.machines[hero.hacking_machine_id]  # type: ignore[index]
        if hero.battery <= 0:
            return Candidate(self._exit_machine(state, hero_id), 0.1, None, "quitter machine: batterie vide")

        # Queued movement and Grappler cutting are forced WAIT ticks.
        if machine.pending_move:
            return Candidate(HeroAction.WAIT, 3.0, ("machine", machine.id), "attendre HACK_MOVE")
        if machine.kind == MachineKind.GRAPPLER and machine.position in state.trees:
            return Candidate(HeroAction.WAIT, 3.0, ("machine", machine.id), "laisser le Grappler couper")

        if machine.kind == MachineKind.EXCAVATOR:
            front = Rules.machine_forward(machine)
            if front in state.holes:
                return Candidate(HeroAction.HACK_FILL, 8.0, ("hole", front.row, front.col), "reboucher trou")
            if not state.holes:
                return Candidate(self._exit_machine(state, hero_id), 0.1, None, "plus de trou utile")

            # Reach a cell adjacent to a hole, then face the hole and fill it.
            goals: set[Position] = set()
            hole_by_goal: dict[Position, list[Position]] = {}
            for hole in state.holes:
                for dr, dc in DIRECTION_VECTORS.values():
                    p = hole.moved(-dr, -dc)
                    if not state.game_map.in_bounds(p):
                        continue
                    if p in state.game_map.rocks or p in state.trees:
                        continue
                    goals.add(p)
                    hole_by_goal.setdefault(p, []).append(hole)
            path = find_machine_path(state, machine, goals)
            if path:
                if len(path) == 1:
                    # Choose an adjacent hole and orient toward it.
                    hole = min(hole_by_goal[machine.position], key=lambda p: (p.row, p.col))
                    dr = hole.row - machine.position.row
                    dc = hole.col - machine.position.col
                    desired = next(d for d, v in DIRECTION_VECTORS.items() if v == (dr, dc))
                    action = self._rotation_action(machine.orientation, desired)
                    return Candidate(action, 5.0, ("hole", hole.row, hole.col), "orienter Excavator vers trou")
                desired = direction_between(path[0], path[1])
                action = self._rotation_action(machine.orientation, desired)
                if action == HeroAction.HACK_MOVE and not Rules.machine_forward_clear(state, machine):
                    return Candidate(HeroAction.WAIT, 0.2, ("machine", machine.id), "chemin machine momentanément bloqué")
                return Candidate(action, 4.0, ("machine", machine.id), "déplacer Excavator vers trou")

        else:  # GRAPPLER
            if not state.trees:
                return Candidate(self._exit_machine(state, hero_id), 0.1, None, "plus d'arbre utile")
            path = find_machine_path(state, machine, set(state.trees))
            if path:
                if len(path) == 1:
                    return Candidate(HeroAction.WAIT, 5.0, ("tree", machine.position.row, machine.position.col), "couper arbre")
                desired = direction_between(path[0], path[1])
                action = self._rotation_action(machine.orientation, desired)
                if action == HeroAction.HACK_MOVE and not Rules.machine_forward_clear(state, machine):
                    return Candidate(HeroAction.WAIT, 0.2, ("machine", machine.id), "chemin machine momentanément bloqué")
                return Candidate(action, 4.0, ("machine", machine.id), "déplacer Grappler vers arbre")

        return Candidate(self._exit_machine(state, hero_id), 0.1, None, "quitter machine sans objectif")

    def _all_candidates(self, state: GameState, hero_id: HeroId) -> list[Candidate]:
        hero = state.heroes[hero_id]
        if hero.is_hacking:
            return [self._control_machine(state, hero_id)]

        reward_candidates = (
            self._chest_candidates(state, hero_id)
            + self._stone_candidates(state, hero_id)
            + self._machine_stone_candidates(state, hero_id)
        )
        reward_candidates.sort(key=lambda c: (-c.utility, c.description))
        if reward_candidates:
            # Keep a few alternatives so pair assignment can avoid target collisions.
            return reward_candidates[:8] + self._compatible_machine_candidates(state, hero_id)[:2]
        return self._compatible_machine_candidates(state, hero_id)[:4]

    def _make_executable(self, state: GameState, hero_id: HeroId, candidate: Candidate) -> HeroAction:
        hero = state.heroes[hero_id]
        if candidate.required_stamina > hero.stamina:
            return HeroAction.WAIT
        # Defensive last-moment validation for physical hero moves/pushes.
        if candidate.action in {
            HeroAction.UP,
            HeroAction.DOWN,
            HeroAction.LEFT,
            HeroAction.RIGHT,
        }:
            move = Rules.hero_move(state, hero, candidate.action)
            if not move.valid:
                return HeroAction.WAIT
        elif candidate.action in PUSH_ACTIONS:
            if not Rules.chest_push(state, hero, candidate.action).valid:
                return HeroAction.WAIT
        return candidate.action

    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]:
        pools: dict[HeroId, list[Candidate]] = {}
        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            candidates = self._all_candidates(state, hero_id)
            # WAIT is always a legal assignment fallback.
            candidates.append(Candidate(HeroAction.WAIT, 0.0, None, "attendre"))
            pools[hero_id] = candidates

        best_pair: tuple[Candidate, Candidate] | None = None
        best_score = float("-inf")
        for f_candidate, m_candidate in product(
            pools[HeroId.IKOTOFOSA], pools[HeroId.IMAHAKI]
        ):
            if (
                f_candidate.target_key is not None
                and f_candidate.target_key == m_candidate.target_key
            ):
                continue
            score = f_candidate.utility + m_candidate.utility
            if score > best_score:
                best_score = score
                best_pair = (f_candidate, m_candidate)

        if best_pair is None:
            best_pair = (
                Candidate(HeroAction.WAIT, 0.0, None, "attendre"),
                Candidate(HeroAction.WAIT, 0.0, None, "attendre"),
            )

        decisions = {
            HeroId.IKOTOFOSA: self._make_executable(state, HeroId.IKOTOFOSA, best_pair[0]),
            HeroId.IMAHAKI: self._make_executable(state, HeroId.IMAHAKI, best_pair[1]),
        }
        self.last_decisions = {
            "F": best_pair[0].description,
            "M": best_pair[1].description,
        }

        has_goal = any(
            candidate.target_key is not None or candidate.utility > 0
            for candidate in best_pair
        )
        if has_goal:
            self.stuck_ticks = 0
        elif all(action == HeroAction.WAIT for action in decisions.values()):
            self.stuck_ticks += 1
        else:
            self.stuck_ticks = 0
        return decisions
