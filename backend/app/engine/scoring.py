from __future__ import annotations
from app.domain.models import GameState

def compute_score(state: GameState) -> int:
    colonne_idx = state.secured_chests
    point = state.total_hero_stones
    s = state.total_stamina
    b = state.total_battery
    t = state.remaining_time
    return colonne_idx * 150 + point * 25 + (s + b) // 4 + t // 2
