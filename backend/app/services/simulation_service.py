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
from app.engine.strategy_v2 import AdaptiveScoreStrategy
from app.engine.strategy_scalable import ScalableStrategy
from app.engine.strategy_v4 import ChestFirstPortfolioStrategy
from app.engine.strategy_v5 import CollaborativePortfolioStrategy
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
        return {'height': game_map.height, 'width': game_map.width, 'time_limit': game_map.time_limit, 'rows': list(game_map.rows), 'coordinate_system': {'origin': 'top-left', 'row_increases': 'down', 'col_increases': 'right'}}

    @staticmethod
    def _event_to_dict(event) -> dict[str, object]:
        return {'type': event.type, 'message': event.message, 'actor': event.actor, 'position': {'row': event.position.row, 'col': event.position.col} if event.position is not None else None, 'data': event.data}

    def _response_from_result(self, *, result: SimulationResult, game_map: GameMap, mission_name: str) -> SimulationResponse:
        etat_final = result.final_snapshot
        entrees_score_final = etat_final['score_inputs']
        props_finaux = etat_final['props']
        ticks = []
        actions = []
        for tick in result.ticks:
            requested = {id_heros.value: action.value for id_heros, action in tick.requested_actions.items()}
            effectif = {id_heros.value: action.value for id_heros, action in tick.effective_actions.items()}
            ticks.append({'tick': tick.tick, 'requested_actions': requested, 'effective_actions': effectif, 'machine_actions': {id_machine: action.value for id_machine, action in tick.machine_actions.items()}, 'events': [self._event_to_dict(evenement) for evenement in tick.events], 'state': tick.snapshot})
            actions.append({'tick': tick.tick, 'F': effectif[HeroId.IKOTOFOSA.value], 'M': effectif[HeroId.IMAHAKI.value]})
        reponse = SimulationResponse.model_validate({'simulation_id': result.simulation_id, 'mission_name': mission_name, 'map': self.map_summary(game_map), 'initial_state': result.initial_snapshot, 'ticks': ticks, 'result': {'score': result.score, 'stones_collected': entrees_score_final['hero_stones'], 'chests_secured': entrees_score_final['secured_chests'], 'chests_lost': props_finaux['lost_chests'], 'remaining_time': etat_final['remaining_time'], 'total_stamina': entrees_score_final['total_stamina'], 'total_battery': entrees_score_final['total_battery'], 'end_reason': etat_final['end_reason']}, 'actions': actions, 'actions_txt': result.actions_text, 'actions_download_url': f'{settings.api_prefix}/simulations/{result.simulation_id}/actions.txt'})
        return reponse

    def _persist(self, response: SimulationResponse) -> None:
        with self._lock:
            self._responses[response.simulation_id] = response
        chemin = settings.output_dir / f'{response.simulation_id}_actions.txt'
        chemin.write_text(response.actions_txt, encoding='utf-8')

    @staticmethod
    def _result_rank(result: SimulationResult) -> tuple[int, int, int, int, int, int, int]:
        etat_final = result.final_snapshot
        entrees_score = etat_final['score_inputs']
        proprietes_etat = etat_final['props']
        return (result.score, int(entrees_score['secured_chests']), int(entrees_score['hero_stones']), -int(proprietes_etat['lost_chests']), int(etat_final['remaining_time']), int(entrees_score['total_stamina']) + int(entrees_score['total_battery']), -len(result.ticks))

    @staticmethod
    def _adaptive_from_options(options: StrategyOptions, *, breadth_multiplier: int=1, stuck_bonus: int=0) -> AdaptiveScoreStrategy:
        return AdaptiveScoreStrategy(max_stones_per_hero=min(100, options.max_stones_per_hero * breadth_multiplier), max_chest_pairs_per_hero=min(100, options.max_chest_pairs_per_hero * breadth_multiplier), max_unlock_obstacles=min(100, options.max_unlock_obstacles * breadth_multiplier), unlock_pair_candidates=min(20, max(2, options.unlock_pair_candidates * breadth_multiplier)), stuck_end_threshold=min(100, options.stuck_end_threshold + stuck_bonus))

    @staticmethod
    def _is_stress_map(game_map: GameMap) -> bool:
        cellules = game_map.height * game_map.width
        charge_coffres = len(game_map.chests) * max(1, len(game_map.bushes))
        return cellules > 2500 or len(game_map.initial_machines) > 12 or len(game_map.stones) > 64 or charge_coffres > 96

    def _run_portfolio(self, game_map: GameMap, options: StrategyOptions) -> SimulationResult:
        if self._is_stress_map(game_map):
            etat = MapParser.build_initial_state(game_map)
            strategie = ScalableStrategy(
                max_stones_per_hero=min(6, options.max_stones_per_hero),
                max_chest_pairs_per_hero=min(2, options.max_chest_pairs_per_hero),
                stuck_end_threshold=max(8, min(24, options.stuck_end_threshold * 2)),
                max_ticks=min(game_map.time_limit, options.scalable_max_ticks),
            )
            return Simulator(etat).run_strategy(strategie)

        fabriques_base = [
            lambda: self._adaptive_from_options(options),
            lambda: HeuristicStrategy(
                max_stones_per_hero=options.max_stones_per_hero,
                max_chest_pairs_per_hero=options.max_chest_pairs_per_hero,
                stuck_end_threshold=options.stuck_end_threshold,
            ),
        ]
        resultats: list[SimulationResult] = []
        for fabrique in fabriques_base:
            etat = MapParser.build_initial_state(game_map)
            resultats.append(Simulator(etat).run_strategy(fabrique()))

        meilleur = max(resultats, key=self._result_rank)
        etat_final = meilleur.final_snapshot
        props_finaux = etat_final.get('props', {})
        coffre_encore_present = bool(props_finaux.get('chests'))
        coffre_perdu = int(props_finaux.get('lost_chests', 0)) > 0

        if meilleur.final_snapshot.get('end_reason') != 'OBJECTIVES_FINISHED' and (coffre_perdu or not coffre_encore_present):
            cellules = game_map.height * game_map.width
            charge_paires_objectifs = len(game_map.chests) * max(1, len(game_map.bushes))
            if cellules <= 2500 and game_map.time_limit <= 2000 and len(game_map.initial_machines) <= 4 and charge_paires_objectifs <= 8 and len(game_map.stones) <= 12:
                etat = MapParser.build_initial_state(game_map)
                resultats.append(Simulator(etat).run_strategy(self._adaptive_from_options(options, breadth_multiplier=2, stuck_bonus=4)))
                meilleur = max(resultats, key=self._result_rank)
        return meilleur

    def _run_portfolio_v4(self, game_map: GameMap, options: StrategyOptions) -> SimulationResult:
        if self._is_stress_map(game_map):
            etat = MapParser.build_initial_state(game_map)
            strategie = ScalableStrategy(
                max_stones_per_hero=min(6, options.max_stones_per_hero),
                max_chest_pairs_per_hero=min(2, options.max_chest_pairs_per_hero),
                stuck_end_threshold=max(8, min(24, options.stuck_end_threshold * 2)),
                max_ticks=min(game_map.time_limit, options.scalable_max_ticks),
            )
            return Simulator(etat).run_strategy(strategie)
        etat = MapParser.build_initial_state(game_map)
        strategie = ChestFirstPortfolioStrategy(
            max_stones_per_hero=options.max_stones_per_hero,
            max_chest_pairs_per_hero=max(12, options.max_chest_pairs_per_hero),
            stuck_end_threshold=max(12, options.stuck_end_threshold * 2),
            max_unlock_checks=min(64, max(16, options.max_unlock_obstacles * 2)),
        )
        return Simulator(etat).run_strategy(strategie)


    def _run_portfolio_v5(self, game_map: GameMap, options: StrategyOptions) -> SimulationResult:
        if self._is_stress_map(game_map):
            etat = MapParser.build_initial_state(game_map)
            strategie = ScalableStrategy(
                max_stones_per_hero=min(6, options.max_stones_per_hero),
                max_chest_pairs_per_hero=min(2, options.max_chest_pairs_per_hero),
                stuck_end_threshold=max(8, min(24, options.stuck_end_threshold * 2)),
                max_ticks=min(game_map.time_limit, options.scalable_max_ticks),
            )
            return Simulator(etat).run_strategy(strategie)
        etat = MapParser.build_initial_state(game_map)
        strategie = CollaborativePortfolioStrategy(
            max_stones_per_hero=options.max_stones_per_hero,
            max_chest_pairs_per_hero=max(16, options.max_chest_pairs_per_hero),
            stuck_end_threshold=max(14, options.stuck_end_threshold * 2),
            max_unlock_checks=min(64, max(16, options.max_unlock_obstacles * 2)),
        )
        return Simulator(etat).run_strategy(strategie)

    def simulate(self, *, map_text: str, mission_name: str, strategy_options: StrategyOptions) -> SimulationResponse:
        carte_jeu = MapParser.parse(map_text)
        if strategy_options.name == 'portfolio_v5':
            resultat = self._run_portfolio_v5(carte_jeu, strategy_options)
        elif strategy_options.name == 'portfolio_v4':
            resultat = self._run_portfolio_v4(carte_jeu, strategy_options)
        elif strategy_options.name == 'portfolio_v3':
            resultat = self._run_portfolio(carte_jeu, strategy_options)
        else:
            etat = MapParser.build_initial_state(carte_jeu)
            if strategy_options.name == 'heuristic_v1':
                strategie = HeuristicStrategy(max_stones_per_hero=strategy_options.max_stones_per_hero, max_chest_pairs_per_hero=strategy_options.max_chest_pairs_per_hero, stuck_end_threshold=strategy_options.stuck_end_threshold)
            elif strategy_options.name == 'scalable_v1':
                strategie = ScalableStrategy(
                    max_stones_per_hero=min(6, strategy_options.max_stones_per_hero),
                    max_chest_pairs_per_hero=min(2, strategy_options.max_chest_pairs_per_hero),
                    stuck_end_threshold=max(8, min(24, strategy_options.stuck_end_threshold * 2)),
                    max_ticks=min(carte_jeu.time_limit, strategy_options.scalable_max_ticks),
                )
            else:
                strategie = self._adaptive_from_options(strategy_options)
            resultat = Simulator(etat).run_strategy(strategie)
        reponse = self._response_from_result(result=resultat, game_map=carte_jeu, mission_name=mission_name)
        self._persist(reponse)
        return reponse

    def replay(self, *, map_text: str, mission_name: str, actions: list[dict[HeroId, HeroAction]], stop_when_objectives_finished: bool=False) -> SimulationResponse:
        carte_jeu = MapParser.parse(map_text)
        if len(actions) > carte_jeu.time_limit:
            raise ValueError(f'Nombre de ticks {len(actions)} supérieur au TIME_LIMIT {carte_jeu.time_limit}.')
        etat = MapParser.build_initial_state(carte_jeu)
        resultat = Simulator(etat).run_actions(actions, stop_when_objectives_finished=stop_when_objectives_finished)
        reponse = self._response_from_result(result=resultat, game_map=carte_jeu, mission_name=mission_name)
        self._persist(reponse)
        return reponse

    def get(self, simulation_id: str) -> SimulationResponse:
        with self._lock:
            reponse = self._responses.get(simulation_id)
        if reponse is None:
            raise SimulationNotFound(simulation_id)
        return reponse

    def actions_path(self, simulation_id: str) -> Path:
        self.get(simulation_id)
        return settings.output_dir / f'{simulation_id}_actions.txt'
simulation_service = SimulationService()
