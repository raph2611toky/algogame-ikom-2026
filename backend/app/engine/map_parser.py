from __future__ import annotations

from dataclasses import replace

from app.domain.enums import ALL_MAP_SYMBOLS, CellSymbol, HeroId, MachineKind, Orientation
from app.domain.models import GameMap, GameState, HeroState, MachineState, Position


class MapFormatError(ValueError):
    pass


class MapParser:
    MAX_DIMENSION = 500
    MAX_CELLS = 100_000
    MAX_TIME_LIMIT = 100_000

    @classmethod
    def parse(cls, text: str) -> GameMap:
        if not isinstance(text, str) or not text.strip():
            raise MapFormatError("Le contenu de map.txt est vide.")

        # Preserve dots/spaces inside map lines, only normalize CRLF and remove
        # trailing newline(s). The official alphabet contains no whitespace symbol.
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
        lines = normalized.split("\n")
        if not lines:
            raise MapFormatError("map.txt ne contient aucune ligne.")

        header = lines[0].strip().split()
        if len(header) != 3:
            raise MapFormatError(
                "La première ligne doit contenir exactement: H W TIME_LIMIT."
            )
        try:
            height, width, time_limit = map(int, header)
        except ValueError as exc:
            raise MapFormatError("H, W et TIME_LIMIT doivent être des entiers.") from exc

        if height <= 0 or width <= 0:
            raise MapFormatError("H et W doivent être strictement positifs.")
        if time_limit <= 0:
            raise MapFormatError("TIME_LIMIT doit être strictement positif.")
        if height > cls.MAX_DIMENSION or width > cls.MAX_DIMENSION:
            raise MapFormatError(
                f"Dimensions trop grandes: maximum {cls.MAX_DIMENSION} par axe."
            )
        if height * width > cls.MAX_CELLS:
            raise MapFormatError(f"Carte trop grande: maximum {cls.MAX_CELLS} cellules.")
        if time_limit > cls.MAX_TIME_LIMIT:
            raise MapFormatError(
                f"TIME_LIMIT trop grand: maximum {cls.MAX_TIME_LIMIT}."
            )

        map_rows = lines[1:]
        if len(map_rows) != height:
            raise MapFormatError(
                f"Nombre de lignes invalide: attendu {height}, reçu {len(map_rows)}."
            )

        for index, row in enumerate(map_rows):
            if len(row) != width:
                raise MapFormatError(
                    f"Largeur invalide à la ligne de carte {index + 1}: "
                    f"attendu {width}, reçu {len(row)}."
                )
            unknown = sorted(set(row) - ALL_MAP_SYMBOLS)
            if unknown:
                raise MapFormatError(
                    f"Symbole(s) inconnu(s) à la ligne {index + 1}: {unknown}."
                )

        rocks: set[Position] = set()
        trees: set[Position] = set()
        holes: set[Position] = set()
        bushes: set[Position] = set()
        stones: set[Position] = set()
        chests: set[Position] = set()
        heroes: dict[HeroId, Position] = {}
        machines: list[MachineState] = []
        machine_counts = {MachineKind.EXCAVATOR: 0, MachineKind.GRAPPLER: 0}

        for r, row in enumerate(map_rows):
            for c, symbol in enumerate(row):
                pos = Position(r, c)
                if symbol == CellSymbol.EMPTY:
                    continue
                if symbol == CellSymbol.ROCK:
                    rocks.add(pos)
                elif symbol == CellSymbol.TREE:
                    trees.add(pos)
                elif symbol == CellSymbol.HOLE:
                    holes.add(pos)
                elif symbol == CellSymbol.BUSH:
                    bushes.add(pos)
                elif symbol == CellSymbol.STONE:
                    stones.add(pos)
                elif symbol == CellSymbol.CHEST:
                    chests.add(pos)
                elif symbol == CellSymbol.IKOTOFOSA:
                    if HeroId.IKOTOFOSA in heroes:
                        raise MapFormatError("La carte contient plusieurs Ikotofosa (F).")
                    heroes[HeroId.IKOTOFOSA] = pos
                elif symbol == CellSymbol.IMAHAKI:
                    if HeroId.IMAHAKI in heroes:
                        raise MapFormatError("La carte contient plusieurs Imahaki (M).")
                    heroes[HeroId.IMAHAKI] = pos
                elif symbol == CellSymbol.EXCAVATOR:
                    kind = MachineKind.EXCAVATOR
                    machine_counts[kind] += 1
                    machines.append(
                        MachineState(
                            id=f"X{machine_counts[kind]}",
                            kind=kind,
                            position=pos,
                            orientation=Orientation.FACING_LEFT,
                        )
                    )
                elif symbol == CellSymbol.GRAPPLER:
                    kind = MachineKind.GRAPPLER
                    machine_counts[kind] += 1
                    machines.append(
                        MachineState(
                            id=f"G{machine_counts[kind]}",
                            kind=kind,
                            position=pos,
                            orientation=Orientation.FACING_RIGHT,
                        )
                    )

        missing = [hero.value for hero in HeroId if hero not in heroes]
        if missing:
            raise MapFormatError(f"Héros manquant(s): {', '.join(missing)}.")

        return GameMap(
            height=height,
            width=width,
            time_limit=time_limit,
            rows=tuple(map_rows),
            rocks=rocks,
            trees=trees,
            holes=holes,
            bushes=bushes,
            stones=stones,
            chests=chests,
            initial_hero_positions=heroes,
            initial_machines=machines,
        )

    @staticmethod
    def build_initial_state(game_map: GameMap) -> GameState:
        heroes = {
            hero_id: HeroState(id=hero_id, position=position)
            for hero_id, position in game_map.initial_hero_positions.items()
        }
        # Deep-enough clone of mutable machine states.
        machines = {
            machine.id: replace(machine)
            for machine in game_map.initial_machines
        }
        return GameState(
            game_map=game_map,
            heroes=heroes,
            machines=machines,
            stones=set(game_map.stones),
            chests=set(game_map.chests),
            trees=set(game_map.trees),
            holes=set(game_map.holes),
        )
