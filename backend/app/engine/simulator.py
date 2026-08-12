from __future__ import annotations

from collections import Counter
from typing import Iterable, Protocol
from uuid import uuid4

from app.domain.enums import (
    HACK_ACTIONS,
    MOVE_ACTIONS,
    PUSH_ACTIONS,
    HeroAction,
    HeroId,
    MachineAction,
    MachineKind,
)
from app.domain.models import Event, GameState, SimulationResult, TickRecord
from app.engine.actions_writer import build_actions_text
from app.engine.rules import Rules
from app.engine.scoring import compute_score
from app.engine.snapshot import snapshot_state


class StrategyProtocol(Protocol):
    def next_actions(self, state: GameState) -> dict[HeroId, HeroAction]: ...
    def should_end(self, state: GameState) -> bool: ...


class Simulator:
    def __init__(self, state: GameState):
        self.state = state
        self.initial_snapshot = snapshot_state(state)
        self.ticks: list[TickRecord] = []

    def _event(
        self,
        events: list[Event],
        type_: str,
        message: str,
        *,
        actor: str | None = None,
        position=None,
        **data: object,
    ) -> None:
        events.append(
            Event(type=type_, message=message, actor=actor, position=position, data=data)
        )

    def _collect_for_hero(self, hero_id: HeroId, events: list[Event]) -> None:
        hero = self.state.heroes[hero_id]
        if hero.position in self.state.stones:
            self.state.stones.remove(hero.position)
            hero.stones += 1
            self._event(
                events,
                "STONE_COLLECTED",
                f"{hero_id.value} récupère une pierre précieuse.",
                actor=hero_id.value,
                position=hero.position,
            )
        self._steal_machine_stones(hero_id, events)

    def _steal_machine_stones(self, hero_id: HeroId, events: list[Event]) -> None:
        hero = self.state.heroes[hero_id]
        for machine in self.state.machines.values():
            if machine.position == hero.position and machine.carried_stones > 0:
                amount = machine.carried_stones
                machine.carried_stones = 0
                hero.stones += amount
                self._event(
                    events,
                    "STONES_STOLEN",
                    f"{hero_id.value} récupère {amount} pierre(s) portée(s) par {machine.id}.",
                    actor=hero_id.value,
                    position=hero.position,
                    machine_id=machine.id,
                    amount=amount,
                )

    def _unhack(self, hero_id: HeroId, events: list[Event]) -> None:
        hero = self.state.heroes[hero_id]
        if not hero.hacking_machine_id:
            return
        machine = self.state.machines[hero.hacking_machine_id]
        machine.hacked_by = None
        machine.pending_move = False
        machine.resume_delay = 1
        hero.hacking_machine_id = None
        self._event(
            events,
            "UNHACK",
            f"{hero_id.value} quitte {machine.id}; la routine automatique reprend après 1 tick.",
            actor=hero_id.value,
            position=hero.position,
            machine_id=machine.id,
        )

    def _apply_chest_destination(self, chest_from, chest_to, events, actor: str) -> None:
        self.state.chests.discard(chest_from)
        if chest_to in self.state.holes:
            self.state.lost_chests += 1
            self._event(
                events,
                "CHEST_LOST",
                "Un coffre tombe dans un trou et est perdu.",
                actor=actor,
                position=chest_to,
            )
        elif chest_to in self.state.game_map.bushes:
            self.state.secured_chests += 1
            self._event(
                events,
                "CHEST_SECURED",
                "Un coffre est placé dans une cachette.",
                actor=actor,
                position=chest_to,
            )
        else:
            self.state.chests.add(chest_to)
            self._event(
                events,
                "CHEST_PUSHED",
                "Un coffre est poussé d'une case.",
                actor=actor,
                position=chest_to,
            )

    def _coerce_wait(
        self,
        hero_id: HeroId,
        effective: dict[HeroId, HeroAction],
        events: list[Event],
        reason: str,
    ) -> None:
        if effective[hero_id] != HeroAction.WAIT:
            self._event(
                events,
                "ACTION_COERCED_TO_WAIT",
                f"Action de {hero_id.value} remplacée par WAIT: {reason}.",
                actor=hero_id.value,
                requested=effective[hero_id].value,
                reason=reason,
            )
        effective[hero_id] = HeroAction.WAIT

    def step(self, requested: dict[HeroId, HeroAction]) -> TickRecord:
        if self.state.ended:
            raise RuntimeError("La partie est déjà terminée.")
        if self.state.elapsed >= self.state.game_map.time_limit:
            self.state.ended = True
            self.state.end_reason = "TIME_LIMIT"
            raise RuntimeError("TIME_LIMIT atteint.")

        events: list[Event] = []
        for machine in self.state.machines.values():
            machine.last_action = MachineAction.NONE

        requested_actions = {
            HeroId.IKOTOFOSA: requested.get(HeroId.IKOTOFOSA, HeroAction.WAIT),
            HeroId.IMAHAKI: requested.get(HeroId.IMAHAKI, HeroAction.WAIT),
        }
        effective = dict(requested_actions)

        controlled_pending_before = {
            mid: machine.pending_move for mid, machine in self.state.machines.items()
        }
        auto_pending_before = {
            mid: machine.auto_move_pending for mid, machine in self.state.machines.items()
        }

        # A queued HACK_MOVE consumes the following tick; the hero must WAIT.
        # A controlled Grappler standing on a tree also consumes a tick to CUT it.
        for hero_id, hero in self.state.heroes.items():
            if hero.hacking_machine_id:
                machine = self.state.machines[hero.hacking_machine_id]
                if controlled_pending_before[machine.id]:
                    self._coerce_wait(hero_id, effective, events, "HACK_MOVE en cours")
                elif machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                    self._coerce_wait(hero_id, effective, events, "Grappler en train de couper un arbre")

        hero_push_actions = {
            hero_id: action
            for hero_id, action in effective.items()
            if action in PUSH_ACTIONS
        }

        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            hero = self.state.heroes[hero_id]
            action = effective[hero_id]

            if action in MOVE_ACTIONS:
                move = Rules.hero_move(self.state, hero, action)
                if not move.valid:
                    self._coerce_wait(hero_id, effective, events, move.reason or "déplacement invalide")
                    continue
                if hero.is_hacking:
                    self._unhack(hero_id, events)
                old = hero.position
                hero.position = move.destination
                hero.stamina -= move.stamina_cost
                self._event(
                    events,
                    "HERO_MOVED",
                    f"{hero_id.value} se déplace.",
                    actor=hero_id.value,
                    position=hero.position,
                    from_row=old.row,
                    from_col=old.col,
                    jumped=move.jumped,
                    stamina_cost=move.stamina_cost,
                )
                self._collect_for_hero(hero_id, events)
                continue

            if action in PUSH_ACTIONS:
                continue

            if action == HeroAction.HACK:
                if hero.is_hacking or hero.battery <= 0:
                    self._coerce_wait(hero_id, effective, events, "HACK invalide")
                    continue
                candidates = [
                    m
                    for m in self.state.machines_at(hero.position)
                    if Rules.compatible_machine(hero, m) and not m.is_hacked
                ]
                if not candidates:
                    self._coerce_wait(hero_id, effective, events, "aucune machine compatible sur la case")
                    continue
                machine = sorted(candidates, key=lambda m: m.id)[0]
                hero.battery -= 1
                hero.hacking_machine_id = machine.id
                machine.hacked_by = hero_id
                machine.auto_move_pending = False
                machine.pending_move = False
                machine.resume_delay = 0
                self._event(
                    events,
                    "MACHINE_HACKED",
                    f"{hero_id.value} prend le contrôle de {machine.id}.",
                    actor=hero_id.value,
                    position=hero.position,
                    machine_id=machine.id,
                )
                continue

            if action in HACK_ACTIONS - {HeroAction.HACK}:
                if not hero.is_hacking or hero.battery <= 0:
                    self._coerce_wait(hero_id, effective, events, "action de hacking invalide")
                    continue
                machine = self.state.machines[hero.hacking_machine_id]  # type: ignore[index]

                if action == HeroAction.HACK_MOVE:
                    if machine.pending_move or not Rules.machine_forward_clear(self.state, machine):
                        self._coerce_wait(hero_id, effective, events, "HACK_MOVE bloqué")
                        continue
                    hero.battery -= 1
                    machine.pending_move = True
                    machine.last_action = MachineAction.MOVE
                    self._event(
                        events,
                        "HACK_MOVE_QUEUED",
                        f"{hero_id.value} programme le déplacement de {machine.id}.",
                        actor=hero_id.value,
                        machine_id=machine.id,
                    )
                elif action == HeroAction.HACK_CW:
                    hero.battery -= 1
                    Rules.rotate_cw(machine)
                    machine.last_action = MachineAction.CW
                    self._event(events, "MACHINE_ROTATED", f"{machine.id} tourne CW.", actor=hero_id.value, machine_id=machine.id)
                elif action == HeroAction.HACK_CCW:
                    hero.battery -= 1
                    Rules.rotate_ccw(machine)
                    machine.last_action = MachineAction.CCW
                    self._event(events, "MACHINE_ROTATED", f"{machine.id} tourne CCW.", actor=hero_id.value, machine_id=machine.id)
                elif action == HeroAction.HACK_FILL:
                    if hero_id != HeroId.IKOTOFOSA or machine.kind != MachineKind.EXCAVATOR:
                        self._coerce_wait(hero_id, effective, events, "HACK_FILL réservé à Ikotofosa/Excavator")
                        continue
                    front = Rules.machine_forward(machine)
                    if front not in self.state.holes:
                        self._coerce_wait(hero_id, effective, events, "aucun trou devant l'excavateur")
                        continue
                    hero.battery -= 1
                    self.state.holes.remove(front)
                    machine.last_action = MachineAction.FILL
                    self._event(events, "HOLE_FILLED", "Un trou est rebouché.", actor=hero_id.value, position=front, machine_id=machine.id)
                elif action == HeroAction.HACK_CUT:
                    if hero_id != HeroId.IMAHAKI or machine.kind != MachineKind.GRAPPLER:
                        self._coerce_wait(hero_id, effective, events, "HACK_CUT réservé à Imahaki/Grappler")
                        continue
                    cut_pos = machine.position if machine.position in self.state.trees else Rules.machine_forward(machine)
                    if cut_pos not in self.state.trees:
                        self._coerce_wait(hero_id, effective, events, "aucun arbre à couper")
                        continue
                    hero.battery -= 1
                    self.state.trees.remove(cut_pos)
                    machine.last_action = MachineAction.CUT
                    self._event(events, "TREE_CUT", "Un arbre est coupé.", actor=hero_id.value, position=cut_pos, machine_id=machine.id)
                continue

            if action != HeroAction.WAIT:
                self._coerce_wait(hero_id, effective, events, "action inconnue")

        push_conflict_machine_ids: set[str] = set()
        valid_hero_pushes: dict[HeroId, object] = {}
        grouped: dict[object, list[tuple[str, object, object]]] = {}

        for hero_id, action in hero_push_actions.items():
            hero = self.state.heroes[hero_id]
            push = Rules.chest_push(self.state, hero, action)
            if not push.valid:
                self._coerce_wait(hero_id, effective, events, push.reason or "poussée invalide")
                continue
            valid_hero_pushes[hero_id] = push
            grouped.setdefault(push.chest_from, []).append((f"hero:{hero_id.value}", push.chest_to, push))

        for mid, machine in self.state.machines.items():
            due = False
            if machine.is_hacked:
                due = controlled_pending_before[mid] and machine.pending_move
            else:
                due = (
                    auto_pending_before[mid]
                    and machine.auto_move_pending
                    and machine.resume_delay == 0
                )
            if not due or not Rules.machine_forward_clear(self.state, machine):
                continue
            chest_from = Rules.machine_forward(machine)
            if chest_from not in self.state.chests:
                continue
            dr = chest_from.row - machine.position.row
            dc = chest_from.col - machine.position.col
            chest_to = chest_from.moved(dr, dc)
            grouped.setdefault(chest_from, []).append((f"machine:{mid}", chest_to, None))

        for chest_from, pushes in grouped.items():
            hero_entries = [entry for entry in pushes if entry[0].startswith("hero:")]
            if not hero_entries:
                continue
            destinations = {entry[1] for entry in pushes}
            if len(destinations) > 1:
                self._event(
                    events,
                    "CHEST_PUSH_CONFLICT",
                    "Plusieurs agents poussent le même coffre dans des directions différentes.",
                    position=chest_from,
                )
                for actor, _dest, _push in pushes:
                    if actor.startswith("hero:"):
                        hero_id = HeroId(actor.split(":", 1)[1])
                        self._coerce_wait(hero_id, effective, events, "conflit de poussée")
                    else:
                        push_conflict_machine_ids.add(actor.split(":", 1)[1])
                continue

            chest_to = next(iter(destinations))
            self._apply_chest_destination(chest_from, chest_to, events, "MULTI_PUSH")
            for actor, _dest, push in hero_entries:
                hero_id = HeroId(actor.split(":", 1)[1])
                hero = self.state.heroes[hero_id]
                if hero.is_hacking:
                    self._unhack(hero_id, events)
                hero.stamina -= 5
                hero.position = push.hero_to
                self._collect_for_hero(hero_id, events)

        move_intents: dict[str, object] = {}
        controlled_move_ids: set[str] = set()
        for mid in sorted(self.state.machines):
            machine = self.state.machines[mid]

            if mid in push_conflict_machine_ids:
                machine.pending_move = False
                machine.auto_move_pending = False
                machine.last_action = MachineAction.WAIT
                self._event(events, "CHEST_PUSH_CONFLICT", f"{mid} est bloqué par un conflit de poussée.", actor=mid)
                continue

            if machine.is_hacked:
                if controlled_pending_before[mid] and machine.pending_move:
                    machine.pending_move = False
                    if Rules.machine_forward_clear(self.state, machine):
                        target = Rules.machine_forward(machine)
                        move_intents[mid] = target
                        controlled_move_ids.add(mid)
                        machine.last_action = MachineAction.MOVE
                    else:
                        machine.last_action = MachineAction.WAIT
                        self._event(events, "MACHINE_MOVE_BLOCKED", f"{mid} ne peut pas exécuter HACK_MOVE.", actor=mid)
                elif machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                    self.state.trees.remove(machine.position)
                    machine.last_action = MachineAction.CUT
                    self._event(events, "TREE_CUT", "Le Grappler coupe automatiquement l'arbre occupé.", actor=mid, position=machine.position)
                continue

            if machine.resume_delay > 0:
                machine.resume_delay -= 1
                machine.last_action = MachineAction.WAIT
                continue

            if machine.kind == MachineKind.GRAPPLER and machine.position in self.state.trees:
                self.state.trees.remove(machine.position)
                machine.last_action = MachineAction.CUT
                self._event(events, "TREE_CUT", "Le Grappler coupe l'arbre occupé.", actor=mid, position=machine.position)
                continue

            if machine.kind == MachineKind.EXCAVATOR and machine.steps_since_dig >= 5:
                self.state.holes.add(machine.position)
                machine.steps_since_dig = 0
                machine.last_action = MachineAction.DIG
                self._event(events, "HOLE_DUG", "L'Excavator creuse un trou.", actor=mid, position=machine.position)
                continue

            if auto_pending_before[mid] and machine.auto_move_pending:
                machine.auto_move_pending = False
                if Rules.machine_forward_clear(self.state, machine):
                    move_intents[mid] = Rules.machine_forward(machine)
                    machine.last_action = MachineAction.MOVE
                else:
                    machine.last_action = MachineAction.WAIT
                    self._event(events, "MACHINE_MOVE_BLOCKED", f"{mid} ne peut pas terminer son déplacement.", actor=mid)
                continue

            if Rules.machine_forward_clear(self.state, machine):
                machine.auto_move_pending = True
                machine.last_action = MachineAction.MOVE
                self._event(events, "MACHINE_MOVE_QUEUED", f"{mid} commence un MOVE de 2 ticks.", actor=mid)
            else:
                if machine.kind == MachineKind.EXCAVATOR:
                    Rules.rotate_ccw(machine)
                    machine.last_action = MachineAction.CCW
                else:
                    Rules.rotate_cw(machine)
                    machine.last_action = MachineAction.CW
                self._event(events, "MACHINE_ROTATED", f"{mid} pivote car son chemin est bloqué.", actor=mid)

        target_counts = Counter(move_intents.values())
        blocked_ids = {
            mid for mid, target in move_intents.items() if target_counts[target] > 1
        }
        for mid in blocked_ids:
            self.state.machines[mid].last_action = MachineAction.WAIT
            self._event(events, "MACHINE_COLLISION_AVOIDED", f"{mid} reste sur place: cible partagée.", actor=mid, position=move_intents[mid])

        for mid in sorted(move_intents):
            if mid in blocked_ids:
                continue
            machine = self.state.machines[mid]
            target = move_intents[mid]
            if any(other.id != mid and other.position == target for other in self.state.machines.values()):
                machine.last_action = MachineAction.WAIT
                self._event(events, "MACHINE_MOVE_BLOCKED", f"{mid} reste sur place: machine sur la cible.", actor=mid, position=target)
                continue

            if target in self.state.chests:
                direction = Rules.machine_forward(machine)
                front_from_machine = target
                dr = front_from_machine.row - machine.position.row
                dc = front_from_machine.col - machine.position.col
                chest_to = front_from_machine.moved(dr, dc)
                if (
                    not self.state.game_map.in_bounds(chest_to)
                    or chest_to in self.state.game_map.rocks
                    or chest_to in self.state.trees
                    or chest_to in self.state.chests
                ):
                    machine.last_action = MachineAction.WAIT
                    self._event(events, "CHEST_PUSH_BLOCKED", f"{mid} ne peut pas pousser le coffre.", actor=mid, position=target)
                    continue
                self._apply_chest_destination(target, chest_to, events, mid)

            old = machine.position
            machine.position = target
            if machine.kind == MachineKind.EXCAVATOR and mid not in controlled_move_ids:
                machine.steps_since_dig += 1

            if machine.hacked_by is not None:
                rider = self.state.heroes[machine.hacked_by]
                rider.position = machine.position

            self._event(
                events,
                "MACHINE_MOVED",
                f"{mid} termine son déplacement.",
                actor=mid,
                position=machine.position,
                from_row=old.row,
                from_col=old.col,
            )

            heroes_here = sorted(
                [h for h in self.state.heroes.values() if h.position == machine.position],
                key=lambda h: h.id.value,
            )
            if machine.position in self.state.stones:
                if heroes_here:
                    self.state.stones.remove(machine.position)
                    heroes_here[0].stones += 1
                    self._event(events, "STONE_COLLECTED", f"{heroes_here[0].id.value} récupère la pierre à l'arrivée de {mid}.", actor=heroes_here[0].id.value, position=machine.position)
                else:
                    self.state.stones.remove(machine.position)
                    machine.carried_stones += 1
                    self._event(events, "STONE_PICKED_BY_MACHINE", f"{mid} ramasse une pierre.", actor=mid, position=machine.position)

            for hero in heroes_here:
                self._steal_machine_stones(hero.id, events)

        for hero_id, hero in self.state.heroes.items():
            if effective[hero_id] == HeroAction.WAIT or hero.is_hacking:
                hero.recovery_seconds += 1
                if hero.recovery_seconds >= 2:
                    if hero.stamina < 100:
                        hero.stamina += 1
                        self._event(events, "STAMINA_RECOVERED", f"{hero_id.value} récupère 1 stamina.", actor=hero_id.value, position=hero.position)
                    hero.recovery_seconds -= 2
            else:
                hero.recovery_seconds = 0

        self.state.elapsed += 1
        if self.state.elapsed >= self.state.game_map.time_limit:
            self.state.ended = True
            self.state.end_reason = "TIME_LIMIT"

        record = TickRecord(
            tick=self.state.elapsed,
            requested_actions=requested_actions,
            effective_actions=dict(effective),
            machine_actions={mid: m.last_action for mid, m in self.state.machines.items()},
            events=events,
            snapshot=snapshot_state(self.state),
        )
        self.ticks.append(record)
        return record

    def run_actions(
        self,
        actions: Iterable[dict[HeroId, HeroAction]],
        *,
        stop_when_objectives_finished: bool = False,
    ) -> SimulationResult:
        for pair in actions:
            if self.state.ended:
                break
            self.step(pair)
            if stop_when_objectives_finished and self.state.objectives_finished:
                self.state.ended = True
                self.state.end_reason = "OBJECTIVES_FINISHED"
                break
        if not self.state.ended:
            self.state.ended = True
            self.state.end_reason = "END_GAME"
        return self.result()

    def run_strategy(self, strategy: StrategyProtocol) -> SimulationResult:
        while not self.state.ended:
            if self.state.objectives_finished:
                self.state.ended = True
                self.state.end_reason = "OBJECTIVES_FINISHED"
                break
            if strategy.should_end(self.state):
                self.state.ended = True
                self.state.end_reason = "STRATEGY_END_GAME"
                break
            self.step(strategy.next_actions(self.state))
        return self.result()

    def result(self) -> SimulationResult:
        return SimulationResult(
            simulation_id=str(uuid4()),
            initial_snapshot=self.initial_snapshot,
            ticks=list(self.ticks),
            final_snapshot=snapshot_state(self.state),
            score=compute_score(self.state),
            actions_text=build_actions_text(self.ticks, self.state.game_map.time_limit),
        )
