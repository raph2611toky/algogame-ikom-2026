from __future__ import annotations

from app.domain.enums import HeroId
from app.domain.models import TickRecord


def build_actions_text(ticks: list[TickRecord], time_limit: int) -> str:
    lines: list[str] = []
    for record in ticks[:time_limit]:
        f_action = record.effective_actions[HeroId.IKOTOFOSA].value
        m_action = record.effective_actions[HeroId.IMAHAKI].value
        lines.append(f"{f_action} | {m_action}")
    lines.append("END_GAME")
    return "\n".join(lines) + "\n"
