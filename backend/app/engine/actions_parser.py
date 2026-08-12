from __future__ import annotations
from app.domain.enums import HeroAction, HeroId

class ActionsFormatError(ValueError):
    pass

def parse_actions_text(text: str, *, time_limit: int) -> list[dict[HeroId, HeroAction]]:
    normalise = text.replace('\r\n', '\n').replace('\r', '\n')
    lignes = [ligne.strip() for ligne in normalise.split('\n') if ligne.strip()]
    if not lignes:
        raise ActionsFormatError('actions.txt est vide.')
    if lignes[-1] != 'END_GAME':
        raise ActionsFormatError('La dernière ligne de actions.txt doit être END_GAME.')
    lignes_actions = lignes[:-1]
    if len(lignes_actions) > time_limit:
        raise ActionsFormatError(f'Trop de ticks: {len(lignes_actions)} > TIME_LIMIT {time_limit}.')
    parsed: list[dict[HeroId, HeroAction]] = []
    for indice, ligne in enumerate(lignes_actions, start=1):
        morceaux = [morceau.strip() for morceau in ligne.split('|')]
        if len(morceaux) != 2:
            raise ActionsFormatError(f"Ligne {indice}: format attendu 'ACTION_F | ACTION_M'.")
        try:
            action_f = HeroAction(morceaux[0])
            action_m = HeroAction(morceaux[1])
        except ValueError as exc:
            raise ActionsFormatError(f'Ligne {indice}: action inconnue ({morceaux[0]!r}, {morceaux[1]!r}).') from exc
        parsed.append({HeroId.IKOTOFOSA: action_f, HeroId.IMAHAKI: action_m})
    return parsed
