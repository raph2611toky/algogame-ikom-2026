from __future__ import annotations

from app.domain.models import GameState


def compute_score(state: GameState) -> int:
    """Formule officiel de GDD.

    R = C*150 + P*25 + ((S+B)//4) + (T//2)
    """
    c = state.secured_chests
    p = state.total_hero_stones
    s = state.total_stamina
    b = state.total_battery
    t = state.remaining_time
    return (c * 150) + (p * 25) + ((s + b) // 4) + (t // 2)
