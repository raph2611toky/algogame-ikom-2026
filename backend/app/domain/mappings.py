from __future__ import annotations

from app.domain.enums import CellSymbol, HeroAction, HeroId, MachineKind, Orientation


SYMBOL_LABELS: dict[CellSymbol, str] = {
    CellSymbol.EMPTY: "empty",
    CellSymbol.IKOTOFOSA: "ikotofosa",
    CellSymbol.IMAHAKI: "imahaki",
    CellSymbol.ROCK: "rock",
    CellSymbol.TREE: "tree",
    CellSymbol.HOLE: "hole",
    CellSymbol.EXCAVATOR: "excavator",
    CellSymbol.GRAPPLER: "grappler",
    CellSymbol.CHEST: "chest",
    CellSymbol.STONE: "stone",
    CellSymbol.BUSH: "bush",
}

HERO_MACHINE_COMPATIBILITY: dict[HeroId, MachineKind] = {
    HeroId.IKOTOFOSA: MachineKind.EXCAVATOR,
    HeroId.IMAHAKI: MachineKind.GRAPPLER,
}

MACHINE_INITIAL_ORIENTATION: dict[MachineKind, Orientation] = {
    MachineKind.EXCAVATOR: Orientation.FACING_LEFT,
    MachineKind.GRAPPLER: Orientation.FACING_RIGHT,
}

ACTION_STAMINA_BASE_COST: dict[HeroAction, int] = {
    HeroAction.UP: 1,
    HeroAction.DOWN: 1,
    HeroAction.LEFT: 1,
    HeroAction.RIGHT: 1,
    HeroAction.WAIT: 0,
    HeroAction.PUSH_UP: 5,
    HeroAction.PUSH_DOWN: 5,
    HeroAction.PUSH_LEFT: 5,
    HeroAction.PUSH_RIGHT: 5,
    HeroAction.HACK: 0,
    HeroAction.HACK_MOVE: 0,
    HeroAction.HACK_FILL: 0,
    HeroAction.HACK_CW: 0,
    HeroAction.HACK_CCW: 0,
    HeroAction.HACK_CUT: 0,
}

HACK_ACTION_BATTERY_COST: dict[HeroAction, int] = {
    HeroAction.HACK: 1,
    HeroAction.HACK_MOVE: 1,
    HeroAction.HACK_FILL: 1,
    HeroAction.HACK_CW: 1,
    HeroAction.HACK_CCW: 1,
    HeroAction.HACK_CUT: 1,
}
