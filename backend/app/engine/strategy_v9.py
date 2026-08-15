from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import (
    ACTION_TO_DIRECTION,
    DIRECTION_VECTORS,
    MOVE_ACTIONS,
    PUSH_ACTIONS,
    HeroAction,
    HeroId,
)
from app.domain.models import GameState, Position
from app.engine.pathfinding import find_path
from app.engine.strategy_v8 import StaminaAwareCollaborativePortfolioStrategy, _DirectRoute


@dataclass(slots=True)
class _ChestSegment:
    """Memoire MINIMALE du pousseur courant d'un coffre entre deux replans v8."""

    chest: Position
    bush: Position
    owner: HeroId
    pushes: int = 0
    last_switch_tick: int = -10_000


@dataclass(slots=True)
class _RelayStage:
    """Point ou le heros de reserve peut se placer pendant un WAIT v8."""

    owner: HeroId
    bush: Position
    target: Position


class StrategicRelayPortfolioStrategy(StaminaAwareCollaborativePortfolioStrategy):
    """portfolio_v9 = portfolio_v8 + une couche de relais, rien d'autre.

    Contrat de cette version:
    - toute la logique principale de portfolio_v8 reste heritee telle quelle;
    - pas d'override du cache route v8, de _route_valid, de la selection du coffre,
      du deblocage, des pierres, du pilotage machine ou de next_actions;
    - on ajoute seulement une affinite de pousseur sur LE MEME coffre afin qu'un
      replan v8 apres un PUSH ne fasse pas F->M->F->M a chaque case;
    - le relais reste autorise quand v8 juge l'autre heros reellement meilleur,
      mais seulement apres un petit segment ou en urgence stamina;
    - quand v8 faisait deja WAIT avec le heros de reserve, celui-ci PEUT rejoindre
      un point de relais s'il peut le faire sans sacrifier sa reserve, puis WAIT.

    Deux coffres distincts continuent donc a etre pousses en parallele exactement
    comme dans v8. Les mecanismes F/X, M/G, carried_stones, safe UNHACK et score
    peak restent ceux de v8 sans modification.
    """

    # Hysteresis volontairement faible: elle ne remplace pas le choix v8, elle
    # empeche seulement le ping-pong push-par-push.
    MIN_SEGMENT_PUSHES = 3
    RELAY_READY_STAMINA = 15
    OWNER_LOW_STAMINA = 10
    RELAY_RUNTIME_GAIN = 4
    RELAY_MIN_GAP_TICKS = 6

    # Staging tres conservateur: on ne remplace qu'un WAIT que v8 avait deja choisi.
    STAGE_MIN_PUSHES = 6
    STAGE_MIN_STAMINA = 50
    STAGE_RESERVE = 25
    STAGE_MAX_TRAVEL_TICKS = 4

    def __init__(
        self,
        *,
        max_stones_per_hero: int = 16,
        max_chest_pairs_per_hero: int = 24,
        stuck_end_threshold: int = 24,
        max_unlock_checks: int = 40,
    ) -> None:
        super().__init__(
            max_stones_per_hero=max_stones_per_hero,
            max_chest_pairs_per_hero=max_chest_pairs_per_hero,
            stuck_end_threshold=stuck_end_threshold,
            max_unlock_checks=max_unlock_checks,
        )
        self._segment: _ChestSegment | None = None
        self._relay_stage: _RelayStage | None = None

    # ------------------------------------------------------------------
    # 1) Affinite du pousseur: v8 choisit toujours le coffre; v9 stabilise seulement
    #    QUI pousse CE MEME coffre entre deux PUSH consecutifs.
    # ------------------------------------------------------------------

    def _route_action(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> HeroAction:
        chest_before = route.expected_chest
        same_segment = bool(
            self._segment is not None
            and self._segment.chest == chest_before
            and self._segment.bush == route.plan.bush
            and self._segment.owner == hero_id
        )

        # Execution 100% portfolio_v8.
        action = super()._route_action(state, hero_id, route)

        if action in PUSH_ACTIONS:
            previous_pushes = self._segment.pushes if same_segment and self._segment else 0
            previous_switch = self._segment.last_switch_tick if same_segment and self._segment else -10_000
            self._segment = _ChestSegment(
                chest=route.expected_chest,  # position attendue APRES le PUSH v8
                bush=route.plan.bush,
                owner=hero_id,
                pushes=previous_pushes + 1,
                last_switch_tick=previous_switch,
            )
        return action

    def _choose_single_direct(self, state: GameState, plans):
        # Le choix de base est calcule d'abord par v8, sans aucun changement.
        base = super()._choose_single_direct(state, plans)
        if base is None or self._segment is None:
            return base

        # Si v8 veut un AUTRE coffre, on ne touche absolument pas a sa decision.
        if base.chest != self._segment.chest:
            return base

        # Si v8 garde deja le meme pousseur, aucune intervention.
        if base.hero_id == self._segment.owner:
            return base

        owner_plan = plans.get((self._segment.owner, self._segment.chest))
        if owner_plan is None:
            # Le pousseur precedent ne peut plus poursuivre legalement: laisser v8
            # changer de heros est indispensable.
            return base

        owner = state.heroes[self._segment.owner]
        helper = state.heroes[base.hero_id]
        owner_key = self._plan_runtime_key(state, owner_plan)
        helper_key = self._plan_runtime_key(state, base)

        emergency = owner.stamina < 5 and helper.stamina >= self.RELAY_READY_STAMINA
        recent_switch = state.elapsed - self._segment.last_switch_tick < self.RELAY_MIN_GAP_TICKS
        segment_ready = self._segment.pushes >= self.MIN_SEGMENT_PUSHES
        helper_ready = helper.stamina >= self.RELAY_READY_STAMINA
        owner_low = owner.stamina <= self.OWNER_LOW_STAMINA
        meaningful_gain = int(helper_key[0]) + self.RELAY_RUNTIME_GAIN < int(owner_key[0])

        allow_relay = emergency or (
            not recent_switch
            and segment_ready
            and helper_ready
            and (owner_low or meaningful_gain)
        )

        if not allow_relay:
            # Meme coffre, meme segment: conserver le pousseur precedent. C'est la
            # seule decision v8 que cette couche stabilise.
            return owner_plan

        self._segment.owner = base.hero_id
        self._segment.pushes = 0
        self._segment.last_switch_tick = state.elapsed
        self._relay_stage = None
        return base


    def _maybe_handoff(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> bool:
        """Handoff v8 intact sauf quand il ne reste qu'un seul coffre.

        Tant qu'il y a plusieurs coffres, on delegue 100% a v8 afin de ne jamais
        perturber sa coordination/deblocage. Sur le DERNIER coffre seulement, on
        evite le ping-pong quand les deux stamina sont faibles.
        """
        if len(state.chests) != 1:
            return super()._maybe_handoff(state, hero_id, route)

        if (
            self._segment is not None
            and self._segment.chest == route.expected_chest
            and self._segment.bush == route.plan.bush
            and self._segment.owner == hero_id
        ):
            owner = state.heroes[hero_id]
            helper = state.heroes[self._other(hero_id)]
            emergency_ready = owner.stamina < 5 and helper.stamina >= self.RELAY_READY_STAMINA
            recent_switch = state.elapsed - self._segment.last_switch_tick < self.RELAY_MIN_GAP_TICKS
            if owner.stamina < 5 and not emergency_ready:
                return False
            if self._segment.pushes < self.MIN_SEGMENT_PUSHES and not emergency_ready:
                return False
            if recent_switch and not emergency_ready:
                return False

        changed = super()._maybe_handoff(state, hero_id, route)
        if changed:
            helper_id = self._other(hero_id)
            if self._segment is None or self._segment.chest != route.expected_chest:
                self._segment = _ChestSegment(route.expected_chest, route.plan.bush, helper_id, 0, state.elapsed)
            else:
                self._segment.owner = helper_id
                self._segment.pushes = 0
                self._segment.last_switch_tick = state.elapsed
            self._relay_stage = None
        return changed

    # ------------------------------------------------------------------
    # 2) Staging facultatif: uniquement a la place d'un WAIT de reserve v8.
    # ------------------------------------------------------------------

    @staticmethod
    def _movement_destination_and_cost(
        state: GameState,
        hero_id: HeroId,
        position: Position,
        action: HeroAction,
    ) -> tuple[Position, int]:
        direction = ACTION_TO_DIRECTION[action]
        dr, dc = DIRECTION_VECTORS[direction]
        adjacent = position.moved(dr, dc)
        if hero_id == HeroId.IKOTOFOSA and adjacent in state.holes:
            return adjacent.moved(dr, dc), 10
        if hero_id == HeroId.IMAHAKI and adjacent in state.trees:
            return adjacent.moved(dr, dc), 10
        return adjacent, 1

    def _future_push_positions(
        self,
        state: GameState,
        owner_id: HeroId,
        route: _DirectRoute,
    ) -> list[Position]:
        hero_pos = route.expected_hero
        chest_pos = route.expected_chest
        result: list[Position] = []
        for action in route.actions:
            if action in MOVE_ACTIONS:
                hero_pos, _cost = self._movement_destination_and_cost(
                    state, owner_id, hero_pos, action
                )
            elif action in PUSH_ACTIONS:
                result.append(hero_pos)
                direction = ACTION_TO_DIRECTION[action]
                dr, dc = DIRECTION_VECTORS[direction]
                hero_pos = chest_pos
                chest_pos = chest_pos.moved(dr, dc)
        return result

    def _stage_target(self, state: GameState, owner_id: HeroId, route: _DirectRoute) -> Position | None:
        positions = self._future_push_positions(state, owner_id, route)
        if len(positions) < self.STAGE_MIN_PUSHES:
            self._relay_stage = None
            return None

        if (
            self._relay_stage is not None
            and self._relay_stage.owner == owner_id
            and self._relay_stage.bush == route.plan.bush
            and self._relay_stage.target in positions
        ):
            return self._relay_stage.target

        # Point proche de la moitie de la portion restante. Le planner/route du coffre
        # n'est PAS modifie: ceci est seulement une destination de marche du helper.
        target = positions[min(len(positions) - 1, max(1, len(positions) // 2))]
        self._relay_stage = _RelayStage(owner=owner_id, bush=route.plan.bush, target=target)
        return target

    def _fill_direct_support(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        assigned: set[Position],
    ) -> dict[HeroId, HeroAction]:
        # D'abord, exactement la logique v8.
        decisions = super()._fill_direct_support(state, decisions, assigned)

        support = self._needs_stamina_support(state, assigned)
        if support is None or decisions.get(support) != HeroAction.WAIT:
            return decisions
        if len(self._direct_routes) != 1:
            return decisions

        owner_id, route = next(iter(self._direct_routes.items()))
        if support != self._other(owner_id):
            return decisions
        helper = state.heroes[support]
        if helper.is_hacking or helper.stamina < self.STAGE_MIN_STAMINA:
            return decisions

        target = self._stage_target(state, owner_id, route)
        if target is None or helper.position == target:
            if target is not None and helper.position == target:
                self.last_decisions[support.value] = (
                    f"attendre au relais ({target.row},{target.col}) et recuperer stamina"
                )
            return decisions

        path = find_path(state, support, target, max_expansions=12_000)
        if path is None or not path.steps:
            return decisions

        # Le deplacement vers le relais doit laisser une vraie reserve. Sinon on garde
        # le WAIT de v8, donc aucune regression de logique/energie.
        if path.total_stamina_cost > helper.stamina - self.STAGE_RESERVE:
            return decisions
        # Staging volontairement LOCAL: si le partenaire est loin, on garde le WAIT
        # v8 au lieu de lui faire depenser de la stamina a travers la carte.
        if path.ticks > self.STAGE_MAX_TRAVEL_TICKS:
            return decisions

        step = path.steps[0]
        if step.stamina_cost > helper.stamina - self.STAGE_RESERVE:
            return decisions
        decisions[support] = step.action
        self.last_decisions[support.value] = (
            f"rejoindre relais ({target.row},{target.col}); le pousseur v8 reste inchangé"
        )
        return decisions
