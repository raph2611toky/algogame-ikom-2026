from __future__ import annotations
from app.domain.enums import HeroId
from app.domain.models import TickRecord

def build_actions_text(ticks: list[TickRecord], time_limit: int) -> str:
    lignes: list[str] = []
    for enregistrement in ticks[:time_limit]:
        action_f = enregistrement.effective_actions[HeroId.IKOTOFOSA].value
        action_m = enregistrement.effective_actions[HeroId.IMAHAKI].value
        lignes.append(f'{action_f} | {action_m}')
    lignes.append('END_GAME')
    return '\n'.join(lignes) + '\n'
