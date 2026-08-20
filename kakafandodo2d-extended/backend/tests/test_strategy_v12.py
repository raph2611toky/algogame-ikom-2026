from pathlib import Path

from app.domain.enums import HeroId, Orientation
from app.domain.models import Position
from app.engine.map_parser import MapParser
from app.engine.simulator import Simulator
from app.engine.strategy_v11 import ProgressiveParallelPortfolioStrategy
from app.engine.strategy_v12 import AddendumAwareParallelPortfolioStrategy


def test_v12_keeps_v11_as_its_direct_parent() -> None:
    assert issubclass(AddendumAwareParallelPortfolioStrategy, ProgressiveParallelPortfolioStrategy)
    # V12 must not replace the core decision loop / chest scheduler. It only
    # adapts addendum-specific meta reasoning.
    assert 'next_actions' not in AddendumAwareParallelPortfolioStrategy.__dict__
    assert '_select_target_chest' not in AddendumAwareParallelPortfolioStrategy.__dict__
    assert '_unlock_actions' not in AddendumAwareParallelPortfolioStrategy.__dict__
    assert '_maybe_handoff' not in AddendumAwareParallelPortfolioStrategy.__dict__


def test_v12_matches_v11_quality_on_legacy_flat_official_sample() -> None:
    game_map = MapParser.parse(Path('maps/official_sample.txt').read_text(encoding='utf-8'))
    results = []
    for cls in (ProgressiveParallelPortfolioStrategy, AddendumAwareParallelPortfolioStrategy):
        state = MapParser.build_initial_state(game_map)
        result = Simulator(state).run_strategy(cls())
        results.append((result.score, len(result.ticks), state.secured_chests, state.total_hero_stones, state.lost_chests))
    assert results[1] == results[0]


def test_v12_hazard_predictor_detects_elevation_cliff_destruction() -> None:
    state = MapParser.build_initial_state(
        MapParser.parse(
            '2 7 50\nG*....X\nF.....M\n',
            '7721111\n1111111\n',
        )
    )
    strategy = AddendumAwareParallelPortfolioStrategy()
    hazard = strategy._predict_autonomous_hazard(state, 'G1', horizon=4)
    assert hazard is not None
    assert hazard.chest_from == Position(0, 1)
    assert hazard.chest_to == Position(0, 2)
    assert hazard.risk >= 100000
    assert 'falaise' in hazard.reason


def test_v12_relocation_recognizes_side_lookahead_machine_blocker() -> None:
    state = MapParser.build_initial_state(
        MapParser.parse(
            '5 8 80\n........\n...X....\n..G...t.\n........\nF......M\n'
        )
    )
    x = state.machines['X1']
    g = state.machines['G1']
    g.orientation = Orientation.FACING_RIGHT
    f = state.heroes[HeroId.IKOTOFOSA]
    f.position = x.position
    f.hacking_machine_id = x.id
    x.hacked_by = HeroId.IKOTOFOSA

    # X is at (1,3), i.e. look-ahead side cell 3 of G moving RIGHT from (2,2).
    assert x.position == Position(1, 3)
    strategy = AddendumAwareParallelPortfolioStrategy()
    plan = strategy._relocation_plan(state, HeroId.IKOTOFOSA, {Position(2, 6)})
    assert plan is not None
    target, control = plan
    assert target != x.position
    assert control.actions


def test_v12_joint_escape_resolves_real_side_lookahead_standoff_without_touching_objectives() -> None:
    """Regression for the lower-corridor stand-off exposed by the 15x20 map.

    X needs to pass downward, but G occupies X's side Look Ahead. G cannot
    simply turn UP and leave because X would then occupy G's side Look Ahead;
    G's current DOWN path is also blocked by a hole. V12 may temporarily park X
    one cell to the right, move G upward, then hand control back to V10/V11.
    """

    class LocalEscapeStrategy(AddendumAwareParallelPortfolioStrategy):
        def _required_obstacles_for_joint_escape(self, state):  # type: ignore[override]
            # Same live obstacle cluster as the real lower corridor. Keeping the
            # objective extraction fixed makes this a fast unit test of the
            # choreography itself, not another chest-planner benchmark.
            return (
                (Position(12, 8), Position(12, 9)),
                (Position(14, 9),),
            )

    state = MapParser.build_initial_state(
        MapParser.parse(Path('maps/evaluation 15x20.txt').read_text(encoding='utf-8'))
    )

    state.chests = {Position(1, 17), Position(13, 1), Position(13, 18)}
    state.holes = {
        Position(1, 13), Position(1, 15), Position(2, 2), Position(3, 18),
        Position(4, 18), Position(4, 19), Position(5, 0), Position(8, 15),
        Position(9, 1), Position(10, 5), Position(12, 8), Position(12, 9),
        Position(13, 0), Position(14, 15),
    }
    state.trees = {
        Position(0, 15), Position(0, 18), Position(1, 5), Position(1, 14),
        Position(3, 19), Position(4, 14), Position(4, 15), Position(4, 16),
        Position(4, 17), Position(6, 5), Position(7, 14), Position(8, 14),
        Position(12, 0), Position(14, 0), Position(14, 9),
    }

    x = state.machines['X1']
    g = state.machines['G1']
    f = state.heroes[HeroId.IKOTOFOSA]
    m = state.heroes[HeroId.IMAHAKI]

    x.position = Position(10, 9)
    x.orientation = Orientation.FACING_DOWN
    x.hacked_by = HeroId.IKOTOFOSA
    x.pending_move = False
    x.auto_move_pending = False
    f.position = x.position
    f.hacking_machine_id = x.id
    f.battery = 71

    g.position = Position(11, 8)
    g.orientation = Orientation.FACING_DOWN
    g.hacked_by = HeroId.IMAHAKI
    g.pending_move = False
    g.auto_move_pending = False
    m.position = g.position
    m.hacking_machine_id = g.id
    m.battery = 81

    # X DOWN is blocked specifically by G in the side Look Ahead cell.
    from app.engine.rules import Rules
    assert Rules.machine_lookahead_reason(state, x) is not None

    strategy = LocalEscapeStrategy()
    path = strategy._plan_joint_escape(state)
    assert path is not None
    assert any(action.value == 'HACK_MOVE' for _machine_id, action in path)
    assert len(path) <= strategy.JOINT_ESCAPE_MAX_TICKS

    chests_before = set(state.chests)
    holes_before = set(state.holes)
    trees_before = set(state.trees)

    assert strategy._install_joint_escape(state, path)
    simulator = Simulator(state)
    while strategy._joint_escape is not None and strategy._joint_escape.actions:
        decisions = {HeroId.IKOTOFOSA: None, HeroId.IMAHAKI: None}
        typed = {
            HeroId.IKOTOFOSA: strategy._joint_escape.actions[0][HeroId.IKOTOFOSA],
            HeroId.IMAHAKI: strategy._joint_escape.actions[0][HeroId.IMAHAKI],
        }
        # Pop/validate through the production continuation path, then execute
        # exactly the resulting pair in the production simulator.
        out = {HeroId.IKOTOFOSA: typed[HeroId.IKOTOFOSA], HeroId.IMAHAKI: typed[HeroId.IMAHAKI]}
        assert strategy._continue_joint_escape(state, out)
        simulator.step(out)

    assert state.chests == chests_before
    assert state.holes == holes_before
    assert state.trees == trees_before
    assert state.machines['X1'].position == Position(10, 10)
    assert state.machines['G1'].position == Position(9, 8)

    # Once parked, at least one normal machine has a short legal route back to
    # productive work on the live corridor obstacles.
    assert (
        strategy._local_productive_machine_path_exists(
            state,
            'X1',
            state.machines['X1'].position,
            state.machines['G1'].position,
            (Position(12, 8), Position(12, 9)),
        )
        or strategy._local_productive_machine_path_exists(
            state,
            'G1',
            state.machines['G1'].position,
            state.machines['X1'].position,
            (Position(14, 9),),
        )
    )
