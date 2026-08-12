import pytest

from app.engine.actions_parser import ActionsFormatError, parse_actions_text


def test_actions_parser() -> None:
    actions = parse_actions_text("LEFT | RIGHT\nWAIT | WAIT\nEND_GAME\n", time_limit=10)
    assert len(actions) == 2


def test_actions_requires_end_game() -> None:
    with pytest.raises(ActionsFormatError):
        parse_actions_text("LEFT | RIGHT\n", time_limit=10)
