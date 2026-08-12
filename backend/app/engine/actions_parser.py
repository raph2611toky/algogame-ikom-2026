from __future__ import annotations

from app.domain.enums import HeroAction, HeroId


class ActionsFormatError(ValueError):
    pass


def parse_actions_text(text: str, *, time_limit: int) -> list[dict[HeroId, HeroAction]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    if not lines:
        raise ActionsFormatError("actions.txt est vide.")
    if lines[-1] != "END_GAME":
        raise ActionsFormatError("La dernière ligne de actions.txt doit être END_GAME.")
    action_lines = lines[:-1]
    if len(action_lines) > time_limit:
        raise ActionsFormatError(
            f"Trop de ticks: {len(action_lines)} > TIME_LIMIT {time_limit}."
        )
    parsed: list[dict[HeroId, HeroAction]] = []
    for index, line in enumerate(action_lines, start=1):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 2:
            raise ActionsFormatError(
                f"Ligne {index}: format attendu 'ACTION_F | ACTION_M'."
            )
        try:
            f_action = HeroAction(parts[0])
            m_action = HeroAction(parts[1])
        except ValueError as exc:
            raise ActionsFormatError(
                f"Ligne {index}: action inconnue ({parts[0]!r}, {parts[1]!r})."
            ) from exc
        parsed.append(
            {HeroId.IKOTOFOSA: f_action, HeroId.IMAHAKI: m_action}
        )
    return parsed
