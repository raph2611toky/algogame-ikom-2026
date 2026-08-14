from __future__ import annotations
from fastapi import APIRouter
from app.domain.enums import HeroAction, Orientation
from app.domain.mappings import SYMBOL_LABELS
from app.schemas.contracts import ContractResponse
from app.engine.strategy_registry import DEFAULT_STRATEGY
router = APIRouter(prefix='/contracts', tags=['contracts'])

@router.get('', response_model=ContractResponse, summary='Lire le contrat Godot ↔ FastAPI', description='Expose les valeurs que Godot peut figer côté client: format de map.txt, symboles, actions des héros, orientations, timing, coûts de ressources et score.', operation_id='get_game_contract')
def get_contract() -> ContractResponse:
    return ContractResponse.model_validate({'version': '1.0', 'map': {'header': 'H W TIME_LIMIT', 'symbols': {libelle: symbole.value for symbole, libelle in SYMBOL_LABELS.items()}, 'origin': 'top-left'}, 'hero_actions': [action.value for action in HeroAction], 'machine_orientations': [orientation.value for orientation in Orientation], 'actions_txt': {'line': 'ACTION_F | ACTION_M', 'terminator': 'END_GAME'}, 'timing': {'relative_seconds_per_tick': 1, 'standard_timescale': 5, 'real_seconds_per_tick': 0.2}, 'resources': {'initial_stamina_per_hero': 100, 'initial_battery_per_hero': 100, 'move_stamina': 1, 'special_hop_or_climb_stamina': 10, 'push_stamina': 5, 'stamina_recovery': '+1 every 2 WAIT/riding ticks', 'battery_per_valid_hack_action': 1}, 'score_formula': 'R = C*150 + P*25 + ((S+B)//4) + (T//2)', 'default_strategy': DEFAULT_STRATEGY})
