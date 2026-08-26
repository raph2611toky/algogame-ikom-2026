from __future__ import annotations

from app.domain.enums import Direction, HeroId, MachineKind
from app.domain.models import GameMap, MachineState, Position


class MapFormatError(ValueError):
    pass


ALLOWED_SYMBOLS = frozenset(".FM#toXG*+@KE")


class MapParser:
    """Parser compatible avec l'ancien format H W TIME_LIMIT.

    Twist 2 ajoute K (gardien) et E (sortie recommandée). E reste optionnel :
    sans sortie, terminer tous les objectifs suffit pour gagner.
    """

    @staticmethod
    def parse(map_text: str, elevation_text: str | None = None) -> GameMap:
        lines = [line.rstrip("\r") for line in map_text.strip().splitlines()]
        if len(lines) < 2:
            raise MapFormatError("map.txt doit contenir un en-tête puis la grille.")
        try:
            height, width, time_limit = (int(value) for value in lines[0].split())
        except (ValueError, TypeError) as exc:
            raise MapFormatError("En-tête attendu : H W TIME_LIMIT_SECONDS.") from exc
        if not (1 <= height <= 200 and 1 <= width <= 200):
            raise MapFormatError("Dimensions autorisées : 1..200.")
        if not (1 <= time_limit <= 86_400):
            raise MapFormatError("TIME_LIMIT_SECONDS doit être compris entre 1 et 86400.")
        rows = lines[1:]
        if len(rows) != height:
            raise MapFormatError(f"La grille doit contenir {height} lignes, reçu {len(rows)}.")
        for index, row in enumerate(rows, start=1):
            if len(row) != width:
                raise MapFormatError(f"Ligne {index}: largeur {len(row)}, attendu {width}.")
            invalid = sorted(set(row) - ALLOWED_SYMBOLS)
            if invalid:
                raise MapFormatError(f"Ligne {index}: symbole(s) inconnu(s) {invalid}.")

        rocks: set[Position] = set()
        trees: set[Position] = set()
        holes: set[Position] = set()
        bushes: set[Position] = set()
        stones: set[Position] = set()
        chests: set[Position] = set()
        exits: set[Position] = set()
        heroes: dict[HeroId, Position] = {}
        guard: Position | None = None
        machines: list[MachineState] = []
        normalized: list[str] = []

        for row_index, row in enumerate(rows):
            normalized_row = list(row)
            for col_index, symbol in enumerate(row):
                pos = Position(row_index, col_index)
                if symbol == "#":
                    rocks.add(pos)
                elif symbol == "t":
                    trees.add(pos)
                elif symbol == "o":
                    holes.add(pos)
                elif symbol == "@":
                    bushes.add(pos)
                elif symbol == "+":
                    stones.add(pos)
                elif symbol == "*":
                    chests.add(pos)
                elif symbol == "E":
                    exits.add(pos)
                elif symbol == "F":
                    if HeroId.IKOTOFOSA in heroes:
                        raise MapFormatError("Ikotofosa F doit apparaître exactement une fois.")
                    heroes[HeroId.IKOTOFOSA] = pos
                    normalized_row[col_index] = "."
                elif symbol == "M":
                    if HeroId.IMAHAKI in heroes:
                        raise MapFormatError("Imahaki M doit apparaître exactement une fois.")
                    heroes[HeroId.IMAHAKI] = pos
                    normalized_row[col_index] = "."
                elif symbol == "K":
                    if guard is not None:
                        raise MapFormatError("Le gardien K doit apparaître exactement une fois.")
                    guard = pos
                    normalized_row[col_index] = "."
                elif symbol in {"X", "G"}:
                    kind = MachineKind(symbol)
                    orientation = Direction.LEFT if kind == MachineKind.EXCAVATOR else Direction.RIGHT
                    machines.append(MachineState(f"{symbol}{len(machines)+1}", kind, pos, orientation))
                    normalized_row[col_index] = "."
            normalized.append("".join(normalized_row))

        missing = [hero.value for hero in HeroId if hero not in heroes]
        if missing:
            raise MapFormatError(f"Héros absent(s) : {', '.join(missing)}.")
        if guard is None:
            raise MapFormatError("Le gardien K est obligatoire dans Twist 2.")

        elevations, has_elevation = MapParser._parse_elevations(
            elevation_text, height, width, rocks
        )
        return GameMap(
            height=height,
            width=width,
            time_limit_seconds=time_limit,
            rows=tuple(normalized),
            elevations=elevations,
            has_elevation=has_elevation,
            rocks=rocks,
            trees=trees,
            holes=holes,
            bushes=bushes,
            initial_stones=stones,
            initial_chests=chests,
            exits=exits,
            initial_heroes=heroes,
            initial_guard=guard,
            initial_machines=machines,
        )

    @staticmethod
    def _parse_elevations(
        text: str | None,
        height: int,
        width: int,
        rocks: set[Position],
    ) -> tuple[tuple[tuple[int, ...], ...], bool]:
        if text is None or not text.strip():
            return tuple(tuple(1 for _ in range(width)) for _ in range(height)), False
        lines = [line.strip() for line in text.strip().splitlines()]
        if len(lines) != height:
            raise MapFormatError(f"elevation.txt doit contenir {height} lignes.")
        parsed: list[tuple[int, ...]] = []
        for row_index, line in enumerate(lines):
            tokens = line.split() if " " in line or "\t" in line else list(line)
            if len(tokens) != width:
                raise MapFormatError(
                    f"Élévation ligne {row_index+1}: {len(tokens)} valeurs, attendu {width}."
                )
            try:
                values = tuple(int(token) for token in tokens)
            except ValueError as exc:
                raise MapFormatError("Les élévations doivent être des entiers 0..9.") from exc
            for col_index, value in enumerate(values):
                pos = Position(row_index, col_index)
                expected_rock = pos in rocks
                if expected_rock and value != 0:
                    raise MapFormatError(f"Le rocher {pos} doit avoir l'élévation 0.")
                if not expected_rock and not 1 <= value <= 9:
                    raise MapFormatError(f"La cellule accessible {pos} doit être entre 1 et 9.")
            parsed.append(values)
        return tuple(parsed), True

