from __future__ import annotations

from fastapi import APIRouter

from app.domain.enums import HeroAction, Orientation
from app.domain.mappings import SYMBOL_LABELS

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("")
def get_contract() -> dict[str, object]:
    return {
        "version": "1.0",
        "map": {
            "header": "H W TIME_LIMIT",
            "symbols": {label: symbol.value for symbol, label in SYMBOL_LABELS.items()},
            "origin": "top-left",
        },
        "hero_actions": [action.value for action in HeroAction],
        "machine_orientations": [orientation.value for orientation in Orientation],
        "actions_txt": {
            "line": "ACTION_F | ACTION_M",
            "terminator": "END_GAME",
        },
        "timing": {
            "relative_seconds_per_tick": 1,
            "standard_timescale": 5,
            "real_seconds_per_tick": 0.2,
        },
        "resources": {
            "initial_stamina_per_hero": 100,
            "initial_battery_per_hero": 100,
            "move_stamina": 1,
            "special_hop_or_climb_stamina": 10,
            "push_stamina": 5,
            "stamina_recovery": "+1 every 2 WAIT/riding ticks",
            "battery_per_valid_hack_action": 1,
        },
        "score_formula": "R = C*150 + P*25 + ((S+B)//4) + (T//2)",
    }
