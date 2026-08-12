from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import Lock

from app.core.config import settings
from app.domain.enums import HeroAction, HeroId
from app.domain.models import GameMap, SimulationResult
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy import HeuristicStrategy
from app.schemas.simulation import SimulationResponse, StrategyOptions


class SimulationNotFound(KeyError):
    pass


class SimulationService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._responses: dict[str, SimulationResponse] = {}
        settings.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def map_summary(game_map: GameMap) -> dict[str, object]:
        return {
            "height": game_map.height,
            "width": game_map.width,
            "time_limit": game_map.time_limit,
            "rows": list(game_map.rows),
            "coordinate_system": {
                "origin": "top-left",
                "row_increases": "down",
                "col_increases": "right",
            },
        }

    @staticmethod
    def _event_to_dict(event) -> dict[str, object]:
        return {
            "type": event.type,
            "message": event.message,
            "actor": event.actor,
            "position": (
                {"row": event.position.row, "col": event.position.col}
                if event.position is not None
                else None
            ),
            "data": event.data,
        }

    def _response_from_result(
        self,
        *,
        result: SimulationResult,
        game_map: GameMap,
        mission_name: str,
    ) -> SimulationResponse:
        final = result.final_snapshot
        final_score_inputs = final["score_inputs"]
        final_props = final["props"]
        ticks = []
        actions = []
        for tick in result.ticks:
            requested = {hid.value: action.value for hid, action in tick.requested_actions.items()}
            effective = {hid.value: action.value for hid, action in tick.effective_actions.items()}
            ticks.append(
                {
                    "tick": tick.tick,
                    "requested_actions": requested,
                    "effective_actions": effective,
                    "machine_actions": {
                        mid: action.value for mid, action in tick.machine_actions.items()
                    },
                    "events": [self._event_to_dict(event) for event in tick.events],
                    "state": tick.snapshot,
                }
            )
            actions.append(
                {
                    "tick": tick.tick,
                    "F": effective[HeroId.IKOTOFOSA.value],
                    "M": effective[HeroId.IMAHAKI.value],
                }
            )

        response = SimulationResponse.model_validate(
            {
                "simulation_id": result.simulation_id,
                "mission_name": mission_name,
                "map": self.map_summary(game_map),
                "initial_state": result.initial_snapshot,
                "ticks": ticks,
                "result": {
                    "score": result.score,
                    "stones_collected": final_score_inputs["hero_stones"],
                    "chests_secured": final_score_inputs["secured_chests"],
                    "chests_lost": final_props["lost_chests"],
                    "remaining_time": final["remaining_time"],
                    "total_stamina": final_score_inputs["total_stamina"],
                    "total_battery": final_score_inputs["total_battery"],
                    "end_reason": final["end_reason"],
                },
                "actions": actions,
                "actions_txt": result.actions_text,
                "actions_download_url": (
                    f"{settings.api_prefix}/simulations/{result.simulation_id}/actions.txt"
                ),
            }
        )
        return response

    def _persist(self, response: SimulationResponse) -> None:
        with self._lock:
            self._responses[response.simulation_id] = response
        path = settings.output_dir / f"{response.simulation_id}_actions.txt"
        path.write_text(response.actions_txt, encoding="utf-8")

    def simulate(
        self,
        *,
        map_text: str,
        mission_name: str,
        strategy_options: StrategyOptions,
    ) -> SimulationResponse:
        game_map = MapParser.parse(map_text)
        state = MapParser.build_initial_state(game_map)
        strategy = HeuristicStrategy(
            max_stones_per_hero=strategy_options.max_stones_per_hero,
            max_chest_pairs_per_hero=strategy_options.max_chest_pairs_per_hero,
            stuck_end_threshold=strategy_options.stuck_end_threshold,
        )
        result = Simulator(state).run_strategy(strategy)
        response = self._response_from_result(
            result=result, game_map=game_map, mission_name=mission_name
        )
        self._persist(response)
        return response

    def replay(
        self,
        *,
        map_text: str,
        mission_name: str,
        actions: list[dict[HeroId, HeroAction]],
        stop_when_objectives_finished: bool = False,
    ) -> SimulationResponse:
        game_map = MapParser.parse(map_text)
        if len(actions) > game_map.time_limit:
            raise ValueError(
                f"Nombre de ticks {len(actions)} supérieur au TIME_LIMIT {game_map.time_limit}."
            )
        state = MapParser.build_initial_state(game_map)
        result = Simulator(state).run_actions(
            actions,
            stop_when_objectives_finished=stop_when_objectives_finished,
        )
        response = self._response_from_result(
            result=result, game_map=game_map, mission_name=mission_name
        )
        self._persist(response)
        return response

    def get(self, simulation_id: str) -> SimulationResponse:
        with self._lock:
            response = self._responses.get(simulation_id)
        if response is None:
            raise SimulationNotFound(simulation_id)
        return response

    def actions_path(self, simulation_id: str) -> Path:
        self.get(simulation_id)
        return settings.output_dir / f"{simulation_id}_actions.txt"


simulation_service = SimulationService()
