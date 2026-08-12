from __future__ import annotations
from dataclasses import replace
from app.domain.enums import ALL_MAP_SYMBOLS, CellSymbol, HeroId, MachineKind, Orientation
from app.domain.models import GameMap, GameState, HeroState, MachineState, Position

class MapFormatError(ValueError):
    pass

class MapParser:
    MAX_DIMENSION = 500
    MAX_CELLS = 100000
    MAX_TIME_LIMIT = 100000

    @classmethod
    def parse(cls, text: str) -> GameMap:
        if not isinstance(text, str) or not text.strip():
            raise MapFormatError('Le contenu de map.txt est vide.')
        normalise = text.replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')
        lignes = normalise.split('\n')
        if not lignes:
            raise MapFormatError('map.txt ne contient aucune ligne.')
        entete = lignes[0].strip().split()
        if len(entete) != 3:
            raise MapFormatError('La première ligne doit contenir exactement: H W TIME_LIMIT.')
        try:
            hauteur, largeur, limite_temps = map(int, entete)
        except ValueError as exc:
            raise MapFormatError('H, W et TIME_LIMIT doivent être des entiers.') from exc
        if hauteur <= 0 or largeur <= 0:
            raise MapFormatError('H et W doivent être strictement positifs.')
        if limite_temps <= 0:
            raise MapFormatError('TIME_LIMIT doit être strictement positif.')
        if hauteur > cls.MAX_DIMENSION or largeur > cls.MAX_DIMENSION:
            raise MapFormatError(f'Dimensions trop grandes: maximum {cls.MAX_DIMENSION} par axe.')
        if hauteur * largeur > cls.MAX_CELLS:
            raise MapFormatError(f'Carte trop grande: maximum {cls.MAX_CELLS} cellules.')
        if limite_temps > cls.MAX_TIME_LIMIT:
            raise MapFormatError(f'TIME_LIMIT trop grand: maximum {cls.MAX_TIME_LIMIT}.')
        lignes_carte = lignes[1:]
        if len(lignes_carte) != hauteur:
            raise MapFormatError(f'Nombre de lignes invalide: attendu {hauteur}, reçu {len(lignes_carte)}.')
        for indice, ligne in enumerate(lignes_carte):
            if len(ligne) != largeur:
                raise MapFormatError(f'Largeur invalide à la ligne de carte {indice + 1}: attendu {largeur}, reçu {len(ligne)}.')
            inconnus = sorted(set(ligne) - ALL_MAP_SYMBOLS)
            if inconnus:
                raise MapFormatError(f'Symbole(s) inconnu(s) à la ligne {indice + 1}: {inconnus}.')
        rochers: set[Position] = set()
        arbres: set[Position] = set()
        trous: set[Position] = set()
        cachettes: set[Position] = set()
        pierres: set[Position] = set()
        coffres: set[Position] = set()
        positions_heros: dict[HeroId, Position] = {}
        machines: list[MachineState] = []
        compteurs_machines = {MachineKind.EXCAVATOR: 0, MachineKind.GRAPPLER: 0}
        for ligne_idx, ligne in enumerate(lignes_carte):
            for colonne_idx, symbole in enumerate(ligne):
                position_courante = Position(ligne_idx, colonne_idx)
                if symbole == CellSymbol.EMPTY:
                    continue
                if symbole == CellSymbol.ROCK:
                    rochers.add(position_courante)
                elif symbole == CellSymbol.TREE:
                    arbres.add(position_courante)
                elif symbole == CellSymbol.HOLE:
                    trous.add(position_courante)
                elif symbole == CellSymbol.BUSH:
                    cachettes.add(position_courante)
                elif symbole == CellSymbol.STONE:
                    pierres.add(position_courante)
                elif symbole == CellSymbol.CHEST:
                    coffres.add(position_courante)
                elif symbole == CellSymbol.IKOTOFOSA:
                    if HeroId.IKOTOFOSA in positions_heros:
                        raise MapFormatError('La carte contient plusieurs Ikotofosa (F).')
                    positions_heros[HeroId.IKOTOFOSA] = position_courante
                elif symbole == CellSymbol.IMAHAKI:
                    if HeroId.IMAHAKI in positions_heros:
                        raise MapFormatError('La carte contient plusieurs Imahaki (M).')
                    positions_heros[HeroId.IMAHAKI] = position_courante
                elif symbole == CellSymbol.EXCAVATOR:
                    type_machine = MachineKind.EXCAVATOR
                    compteurs_machines[type_machine] += 1
                    machines.append(MachineState(id=f'X{compteurs_machines[type_machine]}', kind=type_machine, position=position_courante, orientation=Orientation.FACING_LEFT))
                elif symbole == CellSymbol.GRAPPLER:
                    type_machine = MachineKind.GRAPPLER
                    compteurs_machines[type_machine] += 1
                    machines.append(MachineState(id=f'G{compteurs_machines[type_machine]}', kind=type_machine, position=position_courante, orientation=Orientation.FACING_RIGHT))
        manquants = [heros.value for heros in HeroId if heros not in positions_heros]
        if manquants:
            raise MapFormatError(f"Héros manquant(s): {', '.join(manquants)}.")
        return GameMap(height=hauteur, width=largeur, time_limit=limite_temps, rows=tuple(lignes_carte), rocks=rochers, trees=arbres, holes=trous, bushes=cachettes, stones=pierres, chests=coffres, initial_hero_positions=positions_heros, initial_machines=machines)

    @staticmethod
    def build_initial_state(game_map: GameMap) -> GameState:
        positions_heros = {id_heros: HeroState(id=id_heros, position=position) for id_heros, position in game_map.initial_hero_positions.items()}
        machines = {machine.id: replace(machine) for machine in game_map.initial_machines}
        return GameState(game_map=game_map, heroes=positions_heros, machines=machines, stones=set(game_map.stones), chests=set(game_map.chests), trees=set(game_map.trees), holes=set(game_map.holes))
