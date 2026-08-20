from __future__ import annotations

from copy import deepcopy

from app.domain.models import SimulationResult
from app.engine.actions_writer import build_actions_text


def score_snapshot(snapshot: dict[str, object]) -> int:
    score_inputs = snapshot["score_inputs"]
    assert isinstance(score_inputs, dict)
    return (
        int(score_inputs["secured_chests"]) * 150
        + int(score_inputs["hero_stones"]) * 25
        + (int(score_inputs["total_stamina"]) + int(score_inputs["total_battery"])) // 4
        + int(snapshot["remaining_time"]) // 2
    )


def _snapshot_rank(snapshot: dict[str, object], tick: int) -> tuple[int, int, int, int, int, int, int]:
    score_inputs = snapshot["score_inputs"]
    props = snapshot["props"]
    assert isinstance(score_inputs, dict)
    assert isinstance(props, dict)
    return (
        score_snapshot(snapshot),
        int(score_inputs["secured_chests"]),
        int(score_inputs["hero_stones"]),
        -int(props["lost_chests"]),
        int(snapshot["remaining_time"]),
        int(score_inputs["total_stamina"]) + int(score_inputs["total_battery"]),
        -tick,
    )


def trim_to_best_score_prefix(result: SimulationResult, *, time_limit: int) -> SimulationResult:
    """Conserve le meilleur prefixe strictement meilleur que le score final.

    Le GDD autorise END_GAME avant la limite. Le resultat reste donc un replay
    valide: on garde les ticks jusqu'au meilleur et actions.txt se termine par END_GAME.
    """
    if not result.ticks:
        return result
    best_index = len(result.ticks)
    best_snapshot = result.final_snapshot
    best_rank = _snapshot_rank(result.final_snapshot, len(result.ticks))
    for index, tick in enumerate(result.ticks, start=1):
        rank = _snapshot_rank(tick.snapshot, index)
        if rank > best_rank:
            best_rank = rank
            best_index = index
            best_snapshot = tick.snapshot
    best_score = int(best_rank[0])
    if best_index >= len(result.ticks) or best_score <= result.score:
        return result

    ticks = list(result.ticks[:best_index])
    final_snapshot = deepcopy(best_snapshot)
    final_snapshot["ended"] = True
    final_snapshot["end_reason"] = "BEST_SCORE_END_GAME"
    return SimulationResult(
        simulation_id=result.simulation_id,
        initial_snapshot=result.initial_snapshot,
        ticks=ticks,
        final_snapshot=final_snapshot,
        score=best_score,
        actions_text=build_actions_text(ticks, time_limit),
    )
