from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field

from app.domain.enums import HeroId
from app.domain.models import BalanceConfig, HeroCommand
from app.engine.map_parser import MapParser
from app.engine.rules import health_factor, hero_base_speed
from app.engine.simulator import Simulator
from app.schemas.game import (
    CreateGameRequest,
    EventOut,
    GameSnapshot,
    GuardOut,
    HeroOut,
    MachineOut,
    MapOut,
    ObjectivesOut,
    PositionOut,
    ReplayRequest,
    ReplayResponse,
    TickRequest,
)


class GameNotFound(KeyError):
    pass


class SequenceConflict(ValueError):
    pass


def _position(position) -> PositionOut:
    return PositionOut(row=position.row, col=position.col)


@dataclass(slots=True)
class GameSession:
    simulator: Simulator
    create_request: CreateGameRequest
    last_sequence: int = 0
    responses: dict[int, GameSnapshot] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


class GameService:
    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.RLock()

    def create(self, request: CreateGameRequest) -> GameSnapshot:
        game_map = MapParser.parse(request.map_text, request.elevation_text)
        balance = BalanceConfig(**request.balance.model_dump())
        state = Simulator.initial_state(
            game_map,
            difficulty=request.difficulty,
            seed=request.seed,
            balance=balance,
        )
        state.score = Simulator(state)._score()
        session = GameSession(Simulator(state), request)
        with self._lock:
            self._sessions[state.id] = session
        return self._snapshot(session, sequence=0)

    def get(self, game_id: str) -> GameSnapshot:
        session = self._session(game_id)
        with session.lock:
            return self._snapshot(session, sequence=session.last_sequence)

    def tick(self, game_id: str, request: TickRequest) -> GameSnapshot:
        session = self._session(game_id)
        with session.lock:
            if request.sequence in session.responses:
                duplicate = session.responses[request.sequence].model_copy(deep=True)
                duplicate.duplicate = True
                return duplicate
            expected = session.last_sequence + 1
            if request.sequence != expected:
                raise SequenceConflict(f"Séquence attendue {expected}, reçue {request.sequence}.")
            commands = {
                hero_id: HeroCommand(
                    action=command.action,
                    direction=command.direction,
                    target=command.target,
                )
                for hero_id, command in request.actions.items()
            }
            session.simulator.step(commands)
            session.last_sequence = request.sequence
            response = self._snapshot(session, sequence=request.sequence)
            session.responses[request.sequence] = response.model_copy(deep=True)
            if len(session.responses) > 512:
                del session.responses[min(session.responses)]
            return response

    def reset(self, game_id: str) -> GameSnapshot:
        session = self._session(game_id)
        with session.lock:
            request = session.create_request
            game_map = MapParser.parse(request.map_text, request.elevation_text)
            balance = BalanceConfig(**request.balance.model_dump())
            state = Simulator.initial_state(
                game_map,
                difficulty=request.difficulty,
                seed=request.seed,
                balance=balance,
                game_id=game_id,
            )
            state.score = Simulator(state)._score()
            session.simulator = Simulator(state)
            session.last_sequence = 0
            session.responses.clear()
            return self._snapshot(session, sequence=0)

    def delete(self, game_id: str) -> None:
        with self._lock:
            if self._sessions.pop(game_id, None) is None:
                raise GameNotFound(game_id)

    def replay(self, request: ReplayRequest) -> ReplayResponse:
        create = CreateGameRequest(**request.model_dump(exclude={"ticks"}))
        initial = self.create(create)
        game_id = initial.game_id
        processed = 0
        try:
            final = initial
            for sequence, actions in enumerate(request.ticks, start=1):
                final = self.tick(game_id, TickRequest(sequence=sequence, actions=actions))
                processed = sequence
                if final.status != "ACTIVE":
                    break
            return ReplayResponse(processed_ticks=processed, final=final)
        finally:
            self.delete(game_id)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def _session(self, game_id: str) -> GameSession:
        with self._lock:
            session = self._sessions.get(game_id)
        if session is None:
            raise GameNotFound(game_id)
        return session

    def _snapshot(self, session: GameSession, *, sequence: int) -> GameSnapshot:
        state = session.simulator.state
        game_map = state.game_map
        heroes = {
            hero_id: HeroOut(
                id=hero.id,
                position=_position(hero.position),
                hp=hero.hp,
                stamina=hero.stamina,
                speed_factor=round(hero_base_speed(hero.id) * health_factor(hero.hp), 3),
                cooldown_ticks=hero.cooldown,
                hidden=hero.hidden,
                is_ko=hero.is_ko,
                rescue_ticks=hero.rescue_ticks,
                carrying=hero.carrying,
                carried_by=hero.carried_by,
                healing=hero.heal_ticks_remaining > 0,
            )
            for hero_id, hero in state.heroes.items()
        }
        memory = state.guard.memory
        initial_objectives = len(game_map.initial_stones) + len(game_map.initial_chests)
        completed_objectives = state.collected_stones + state.secured_chests
        progress = 100.0 if initial_objectives == 0 else 100 * completed_objectives / initial_objectives
        return GameSnapshot(
            game_id=state.id,
            sequence=sequence,
            version=state.version,
            status=state.status,
            end_reason=state.end_reason,
            difficulty=state.difficulty,
            elapsed_ticks=state.elapsed_ticks,
            remaining_seconds=round(state.remaining_seconds, 3),
            telemetry_score=state.score,
            mission_progress_percent=round(progress, 2),
            heroes=heroes,
            guard=GuardOut(
                position=_position(state.guard.position),
                orientation=state.guard.orientation,
                mode=memory.mode,
                cooldown_ticks=state.guard.cooldown,
                intended_destination=(
                    _position(state.guard.intended_destination)
                    if state.guard.intended_destination is not None
                    else None
                ),
                visible_heroes=sorted(memory.visible, key=lambda value: value.value),
                detection=memory.detection,
            ),
            machines=[
                MachineOut(
                    id=machine.id,
                    kind=machine.kind.value,
                    position=_position(machine.position),
                    orientation=machine.orientation,
                    cooldown_ticks=machine.cooldown,
                )
                for machine in sorted(state.machines.values(), key=lambda item: item.id)
            ],
            objectives=ObjectivesOut(
                stones_collected=state.collected_stones,
                stones_remaining=len(state.stones),
                chests_secured=state.secured_chests,
                chests_remaining=len(state.chests),
                healing_charges=state.healing_charges,
            ),
            stones=[_position(pos) for pos in sorted(state.stones)],
            chests=[_position(pos) for pos in sorted(state.chests)],
            events=[
                EventOut(
                    type=event.type,
                    message=event.message,
                    actor=event.actor,
                    position=_position(event.position) if event.position is not None else None,
                    data=event.data,
                )
                for event in state.events
            ],
            map=MapOut(
                height=game_map.height,
                width=game_map.width,
                time_limit_seconds=game_map.time_limit_seconds,
                tick_ms=state.balance.tick_ms,
                has_elevation=game_map.has_elevation,
                elevations=[list(row) for row in game_map.elevations],
                rocks=[_position(pos) for pos in sorted(game_map.rocks)],
                trees=[_position(pos) for pos in sorted(state.trees)],
                holes=[_position(pos) for pos in sorted(state.holes)],
                bushes=[_position(pos) for pos in sorted(game_map.bushes)],
                exits=[_position(pos) for pos in sorted(game_map.exits)],
            ),
        )


game_service = GameService()
