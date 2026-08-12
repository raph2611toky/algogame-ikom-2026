from __future__ import annotations
from typing import Literal
from pydantic import Field
from app.domain.enums import HeroAction
from app.schemas.common import APIModel, PositionSchema
OFFICIAL_SAMPLE_MAP = '5 7 100\nG+.M..+\n.###tt#\n.o*.+.@\no##t#tX\n.F#++..'

class MissionInput(APIModel):
    name: str = Field(default='mission', min_length=1, max_length=120, description='Nom libre de la mission côté Godot.')
    map_text: str = Field(min_length=1, max_length=1000000, description='Contenu complet de map.txt: première ligne H W TIME_LIMIT puis H lignes ASCII.')
    model_config = {'extra': 'forbid', 'json_schema_extra': {'example': {'name': 'official_sample', 'map_text': OFFICIAL_SAMPLE_MAP}}}

class StrategyOptions(APIModel):
    name: Literal['portfolio_v3', 'adaptive_v2', 'heuristic_v1'] = Field(default='portfolio_v3', description='portfolio_v3 pré-calcule plusieurs plans conformes au GDD et conserve celui qui obtient réellement le meilleur score dans le moteur local. adaptive_v2 est le planificateur score-aware/ability-aware; heuristic_v1 reste la baseline.')
    max_stones_per_hero: int = Field(default=16, ge=1, le=100)
    max_chest_pairs_per_hero: int = Field(default=12, ge=1, le=100)
    max_unlock_obstacles: int = Field(default=20, ge=1, le=100, description='Nombre maximal de trous/arbres candidats analysés pour leur valeur de déblocage.')
    unlock_pair_candidates: int = Field(default=8, ge=2, le=20, description='Frontière utilisée pour détecter les chaînes de deux obstacles nécessaires.')
    stuck_end_threshold: int = Field(default=8, ge=1, le=100)

class SimulationRequest(APIModel):
    mission: MissionInput
    strategy: StrategyOptions = Field(default_factory=StrategyOptions)
    model_config = {'extra': 'forbid', 'json_schema_extra': {'example': {'mission': {'name': 'official_sample', 'map_text': OFFICIAL_SAMPLE_MAP}, 'strategy': {'name': 'portfolio_v3', 'max_stones_per_hero': 16, 'max_chest_pairs_per_hero': 12, 'max_unlock_obstacles': 20, 'unlock_pair_candidates': 8, 'stuck_end_threshold': 8}}}}

class ReplayActionPair(APIModel):
    F: HeroAction = HeroAction.WAIT
    M: HeroAction = HeroAction.WAIT

class ReplayRequest(APIModel):
    mission: MissionInput
    actions: list[ReplayActionPair] = Field(default_factory=list)
    stop_when_objectives_finished: bool = False
    model_config = {'extra': 'forbid', 'json_schema_extra': {'example': {'mission': {'name': 'replay_demo', 'map_text': OFFICIAL_SAMPLE_MAP}, 'actions': [{'F': 'LEFT', 'M': 'LEFT'}, {'F': 'UP', 'M': 'LEFT'}, {'F': 'RIGHT', 'M': 'HACK'}], 'stop_when_objectives_finished': False}}}

class ReplayTextRequest(APIModel):
    mission: MissionInput
    actions_text: str = Field(min_length=1, max_length=5000000)
    model_config = {'extra': 'forbid', 'json_schema_extra': {'example': {'mission': {'name': 'replay_text_demo', 'map_text': OFFICIAL_SAMPLE_MAP}, 'actions_text': 'LEFT | LEFT\nUP | LEFT\nRIGHT | HACK\nEND_GAME\n'}}}

class ScoreInputsSchema(APIModel):
    secured_chests: int
    hero_stones: int
    total_stamina: int
    total_battery: int

class HeroSnapshotSchema(APIModel):
    position: PositionSchema
    stamina: int
    battery: int
    stones: int
    hacking_machine_id: str | None = None

class MachineSnapshotSchema(APIModel):
    kind: str
    position: PositionSchema
    orientation: str
    hacked_by: str | None = None
    carried_stones: int
    pending_move: bool
    auto_move_pending: bool
    steps_since_dig: int
    last_action: str

class PropsSnapshotSchema(APIModel):
    stones: list[PositionSchema]
    chests: list[PositionSchema]
    trees: list[PositionSchema]
    holes: list[PositionSchema]
    bushes: list[PositionSchema]
    rocks: list[PositionSchema]
    secured_chests: int
    lost_chests: int

class StateSnapshotSchema(APIModel):
    elapsed: int
    remaining_time: int
    score_inputs: ScoreInputsSchema
    heroes: dict[str, HeroSnapshotSchema]
    machines: dict[str, MachineSnapshotSchema]
    props: PropsSnapshotSchema
    ended: bool
    end_reason: str | None = None

class EventSchema(APIModel):
    type: str
    message: str
    actor: str | None = None
    position: PositionSchema | None = None
    data: dict[str, object] = Field(default_factory=dict)

class TickSchema(APIModel):
    tick: int
    requested_actions: dict[str, HeroAction]
    effective_actions: dict[str, HeroAction]
    machine_actions: dict[str, str]
    events: list[EventSchema]
    state: StateSnapshotSchema

class ResultSummarySchema(APIModel):
    score: int
    stones_collected: int
    chests_secured: int
    chests_lost: int
    remaining_time: int
    total_stamina: int
    total_battery: int
    end_reason: str | None = None

class CoordinateSystemSchema(APIModel):
    origin: Literal['top-left'] = 'top-left'
    row_increases: Literal['down'] = 'down'
    col_increases: Literal['right'] = 'right'

class SimulationMapSchema(APIModel):
    height: int = Field(gt=0)
    width: int = Field(gt=0)
    time_limit: int = Field(gt=0)
    rows: list[str]
    coordinate_system: CoordinateSystemSchema

class ActionTickSchema(APIModel):
    tick: int = Field(ge=1)
    F: HeroAction
    M: HeroAction

class SimulationResponse(APIModel):
    contract_version: Literal['1.0'] = '1.0'
    simulation_id: str
    mission_name: str
    map: SimulationMapSchema
    initial_state: StateSnapshotSchema
    ticks: list[TickSchema]
    result: ResultSummarySchema
    actions: list[ActionTickSchema]
    actions_txt: str
    actions_download_url: str
