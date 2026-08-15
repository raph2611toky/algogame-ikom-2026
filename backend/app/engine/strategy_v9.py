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
from app.engine.rules import Rules
from app.engine.strategy_v4 import DirectChestPlan
from app.engine.strategy_v8 import (
    StaminaAwareCollaborativePortfolioStrategy,
    _DirectRoute,
)


@dataclass(slots=True)
class _PushMilestone:
    """Etat geometrique juste avant un PUSH du plan coffre courant."""

    push_number: int
    action_index: int
    action: HeroAction
    hero_position: Position
    chest_position: Position
    stamina_before_push: int


@dataclass(slots=True)
class _RelayAssignment:
    """Relais planifie: un seul pousseur actif, un second heros se prepare."""

    owner: HeroId
    helper: HeroId
    bush: Position
    stage_target: Position
    handoff_chest: Position
    handoff_push_number: int
    created_at: int
    reason: str


class StrategicRelayPortfolioStrategy(StaminaAwareCollaborativePortfolioStrategy):
    """
    portfolio_v9 = portfolio_v8 + relais strategique de pousseur.

    Principes ajoutes sans modifier les regles du moteur:
    - un coffre n'a jamais deux pousseurs planifies au meme tick;
    - on evite le ping-pong F/M a chaque PUSH: un pousseur garde un segment;
    - pour un long coffre, le second heros se place a un point de relais puis WAIT
      afin de recuperer sa stamina pendant que le coffre approche;
    - relais immediat possible si le pousseur est a bout et l'autre a une vraie reserve;
    - apres un relais, l'ancien pousseur ne reprend pas aussitot le meme coffre;
    - si l'ancien pousseur est le seul capable de debloquer un autre coffre (F/trou,
      M/arbre), ce travail specialise passe avant la preparation d'un nouveau relais;
    - avec deux coffres directement poussables et distincts, le parallele v8 est conserve.
    """

    RELAY_RESERVE = 12
    RELAY_READY_STAMINA = 15
    RELAY_REENTRY_STAMINA = 24
    RELAY_MIN_GAP_TICKS = 10
    RELAY_MIN_SEGMENT_PUSHES = 2

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
        self._relay: _RelayAssignment | None = None
        self._last_handoff_tick = -10_000
        self._last_handoff_from: HeroId | None = None
        self._pushes_since_handoff: dict[HeroId, int] = {
            HeroId.IKOTOFOSA: 0,
            HeroId.IMAHAKI: 0,
        }
        self._specialist_priority_until: dict[HeroId, int] = {}

    # ------------------------------------------------------------------
    # Geometry / relay planning
    # ------------------------------------------------------------------

    @staticmethod
    def _route_topology_signature(state: GameState, tracked_chest: Position) -> tuple[object, ...]:
        """Signature dynamique d'une route qui ignore UNIQUEMENT son propre coffre.

        v8 utilisait la signature globale incluant la position du coffre suivi. Apres
        chaque PUSH, la position changeait donc la signature et le cache etait jete,
        ce qui pouvait replanifier F puis M puis F et creer un pseudo-relais a chaque
        case. Ici le mouvement attendu du coffre ne casse pas le plan, alors qu'un
        DIG/CUT/FILL ou le mouvement d'un autre coffre l'invalide toujours.
        """
        return (
            tuple(sorted((p.row, p.col) for p in state.chests if p != tracked_chest)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(sorted((p.row, p.col) for p in state.game_map.rocks)),
            tuple(sorted((p.row, p.col) for p in state.game_map.bushes)),
        )

    def _cache_route(self, state: GameState, plan: DirectChestPlan) -> _DirectRoute:
        route = super()._cache_route(state, plan)
        route.topology_signature = self._route_topology_signature(state, route.expected_chest)
        return route

    def _route_valid(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> bool:
        if route.expected_chest not in state.chests:
            return False
        if state.heroes[hero_id].position != route.expected_hero:
            return False
        if route.plan.bush not in state.game_map.bushes:
            return False
        if not route.actions:
            return False
        return route.topology_signature == self._route_topology_signature(
            state, route.expected_chest
        )


    @staticmethod
    def _movement_destination(
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

    def _push_milestones(
        self,
        state: GameState,
        hero_id: HeroId,
        route: _DirectRoute,
    ) -> list[_PushMilestone]:
        hero_position = route.expected_hero
        chest_position = route.expected_chest
        stamina_spent = 0
        push_number = 0
        milestones: list[_PushMilestone] = []
        for action_index, action in enumerate(route.actions):
            if action in MOVE_ACTIONS:
                hero_position, cost = self._movement_destination(
                    state, hero_id, hero_position, action
                )
                stamina_spent += cost
                continue
            if action in PUSH_ACTIONS:
                push_number += 1
                milestones.append(
                    _PushMilestone(
                        push_number=push_number,
                        action_index=action_index,
                        action=action,
                        hero_position=hero_position,
                        chest_position=chest_position,
                        stamina_before_push=stamina_spent,
                    )
                )
                direction = ACTION_TO_DIRECTION[action]
                dr, dc = DIRECTION_VECTORS[direction]
                hero_position = chest_position
                chest_position = chest_position.moved(dr, dc)
                stamina_spent += 5
        return milestones

    @staticmethod
    def _cheap_specialist_pressure(
        state: GameState,
        hero_id: HeroId,
        *,
        excluded_chest: Position,
    ) -> bool:
        """Heuristique O(coffres*obstacles), sans lancer le planner de deblocage.

        Le test exact _unlock_profile est volontairement evite dans la boucle de
        relais: sur les cartes 15x20 complexes il peut couter plusieurs secondes.
        Une confirmation exacte sera faite plus tard par _secondary_unlock_action.
        """
        if len(state.chests) <= 1:
            return False
        owner_obstacles = state.holes if hero_id == HeroId.IKOTOFOSA else state.trees
        partner_obstacles = state.trees if hero_id == HeroId.IKOTOFOSA else state.holes
        if not owner_obstacles:
            return False
        for chest in state.chests:
            if chest == excluded_chest:
                continue
            owner_near = any(chest.manhattan(obstacle) <= 4 for obstacle in owner_obstacles)
            partner_near = any(chest.manhattan(obstacle) <= 4 for obstacle in partner_obstacles)
            # On anticipe surtout le cas demande: l'autre coffre depend clairement
            # de la capacite du proprietaire actuel, pas d'un deblocage mixte ambigu.
            if owner_near and not partner_near:
                return True
        return False

    def _relay_candidate_indices(
        self,
        state: GameState,
        owner_id: HeroId,
        route: _DirectRoute,
        milestones: list[_PushMilestone],
    ) -> list[int]:
        owner = state.heroes[owner_id]
        helper_id = self._other(owner_id)
        helper = state.heroes[helper_id]
        push_count = len(milestones)
        if push_count < 2:
            return []
        # Un coffre court se termine plus vite avec son proprietaire actuel. Faire
        # venir le partenaire pour 2-5 PUSH gaspille du mouvement et peut detourner
        # un heros qui collecte/debloque ailleurs. Exception: proprietaire presque
        # vide, ou le relais est reellement necessaire pour continuer.
        if push_count < 6 and owner.stamina >= max(10, route.remaining_stamina):
            return []

        specialist_pressure = self._cheap_specialist_pressure(
            state, owner_id, excluded_chest=route.expected_chest
        )

        # Si le proprietaire peut terminer avec une marge confortable et qu'il n'a
        # aucun autre travail exclusif a faire, le relais serait une depense de temps.
        if not specialist_pressure and owner.stamina >= route.remaining_stamina + self.RELAY_RESERVE:
            return []

        # Segment souhaite: 1/3 si le proprietaire doit rapidement repartir sur un
        # autre coffre specialise, sinon environ la moitie. Si le pousseur est deja
        # presque vide, on vise le premier relais raisonnablement atteignable.
        if specialist_pressure:
            desired_completed = max(1, push_count // 3)
        elif owner.stamina <= 10 and helper.stamina >= self.RELAY_READY_STAMINA:
            desired_completed = 1
        else:
            desired_completed = max(1, push_count // 2)

        # Ne pas planifier au-dela de ce que le pousseur peut depenser tout en gardant
        # une petite reserve. stamina_before_push est le cout pour atteindre le PUSH
        # de relais; les PUSH precedents appartiennent donc au segment du proprietaire.
        budget = max(0, owner.stamina - self.RELAY_RESERVE)
        affordable_completed = 0
        for milestone in milestones:
            if milestone.stamina_before_push <= budget:
                affordable_completed = max(affordable_completed, milestone.push_number - 1)
        if affordable_completed > 0:
            desired_completed = min(desired_completed, affordable_completed)

        # L'index vise le PUSH que fera le nouveau pousseur.
        target_index = min(push_count - 1, max(1, desired_completed))
        order = list(range(target_index, push_count)) + list(range(target_index - 1, 0, -1))
        return order

    def _build_relay(
        self,
        state: GameState,
        owner_id: HeroId,
        route: _DirectRoute,
    ) -> _RelayAssignment | None:
        if len(self._direct_routes) != 1:
            return None
        helper_id = self._other(owner_id)
        helper = state.heroes[helper_id]
        if helper_id in self._direct_routes:
            return None
        milestones = self._push_milestones(state, owner_id, route)
        indices = self._relay_candidate_indices(state, owner_id, route, milestones)
        if not indices:
            return None

        specialist_pressure = self._cheap_specialist_pressure(
            state, owner_id, excluded_chest=route.expected_chest
        )
        reason = "liberer le specialiste pour un autre coffre" if specialist_pressure else "relais stamina sur long trajet"

        # On choisit un point que le helper peut effectivement rejoindre. Une marge
        # de 2 ticks evite de l'envoyer vers un point que le coffre atteindra avant lui.
        for idx in indices:
            milestone = milestones[idx]
            path = find_path(
                state,
                helper_id,
                milestone.hero_position,
                max_expansions=12_000,
            )
            if path is None:
                continue
            ticks_before_handoff = milestone.action_index
            if path.ticks > ticks_before_handoff and idx < len(milestones) - 1:
                continue
            return _RelayAssignment(
                owner=owner_id,
                helper=helper_id,
                bush=route.plan.bush,
                stage_target=milestone.hero_position,
                handoff_chest=milestone.chest_position,
                handoff_push_number=milestone.push_number,
                created_at=state.elapsed,
                reason=reason,
            )
        return None

    def _ensure_relay(self, state: GameState) -> _RelayAssignment | None:
        if len(self._direct_routes) != 1:
            self._relay = None
            return None
        owner_id, route = next(iter(self._direct_routes.items()))
        if not self._route_valid(state, owner_id, route):
            self._relay = None
            return None
        if (
            self._relay is not None
            and self._relay.owner == owner_id
            and self._relay.helper == self._other(owner_id)
            and self._relay.bush == route.plan.bush
        ):
            future_positions = {
                milestone.chest_position
                for milestone in self._push_milestones(state, owner_id, route)
            }
            if (
                route.expected_chest == self._relay.handoff_chest
                or self._relay.handoff_chest in future_positions
            ):
                return self._relay
        self._relay = self._build_relay(state, owner_id, route)
        return self._relay

    def _relay_support_action(
        self,
        state: GameState,
        relay: _RelayAssignment,
    ) -> HeroAction:
        helper = state.heroes[relay.helper]
        if helper.position == relay.stage_target:
            self.last_decisions[relay.helper.value] = (
                f"attendre au relais ({relay.stage_target.row},{relay.stage_target.col}) "
                "et recharger stamina"
            )
            return HeroAction.WAIT
        path = find_path(
            state,
            relay.helper,
            relay.stage_target,
            max_expansions=12_000,
        )
        if path is None or not path.steps:
            self.last_decisions[relay.helper.value] = "relais inaccessible pour l'instant; recuperer stamina"
            return HeroAction.WAIT
        step = path.steps[0]
        if step.stamina_cost > helper.stamina:
            self.last_decisions[relay.helper.value] = "recharger stamina avant de rejoindre le point de relais"
            return HeroAction.WAIT
        self.last_decisions[relay.helper.value] = (
            f"rejoindre relais coffre ({relay.stage_target.row},{relay.stage_target.col})"
        )
        return step.action

    # ------------------------------------------------------------------
    # Handoff policy: segment based, not push-by-push ping-pong
    # ------------------------------------------------------------------

    def _handoff_allowed_by_hysteresis(
        self,
        state: GameState,
        owner_id: HeroId,
        helper_id: HeroId,
        *,
        emergency: bool,
    ) -> bool:
        if emergency:
            return True
        if state.elapsed - self._last_handoff_tick < self.RELAY_MIN_GAP_TICKS:
            return False
        # Apres F->M, F ne reprend pas 2 ticks plus tard juste parce qu'il a 6 stamina.
        # Il doit avoir reconstitue une vraie reserve, sauf urgence du pousseur actuel.
        if self._last_handoff_from == helper_id:
            if state.heroes[helper_id].stamina < self.RELAY_REENTRY_STAMINA:
                return False
        if self._pushes_since_handoff.get(owner_id, 0) < self.RELAY_MIN_SEGMENT_PUSHES:
            return False
        return True

    def _perform_handoff(
        self,
        state: GameState,
        owner_id: HeroId,
        route: _DirectRoute,
        takeover: DirectChestPlan,
        *,
        reason: str,
    ) -> bool:
        helper_id = takeover.hero_id
        self._direct_routes.pop(owner_id, None)
        self._hero_chest_targets[owner_id] = None
        self._cache_route(state, takeover)
        self._hero_chest_targets[helper_id] = takeover.chest
        self._last_handoff_tick = state.elapsed
        self._last_handoff_from = owner_id
        self._pushes_since_handoff[helper_id] = 0
        # Evaluation couteuse faite UNE SEULE fois au moment du relais. On evite de
        # recalculer les profils de tous les coffres a chaque tick de PUSH.
        if self._cheap_specialist_pressure(
            state, owner_id, excluded_chest=route.expected_chest
        ):
            self._specialist_priority_until[owner_id] = state.elapsed + 40
        self._relay = None
        self.last_decisions[owner_id.value] = (
            f"relais coffre ({route.expected_chest.row},{route.expected_chest.col}) "
            f"vers {helper_id.value}: {reason}"
        )
        return True

    def _maybe_handoff(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> bool:
        # Remplace le handoff v8 base sur la stamina TOTALE restante du plan. Ce
        # critere pouvait provoquer F->M->F->M a chaque nouvelle position du coffre.
        if len(self._direct_routes) != 1:
            return False
        relay = self._ensure_relay(state)
        helper_id = self._other(hero_id)
        helper = state.heroes[helper_id]
        owner = state.heroes[hero_id]
        next_action = route.actions[0] if route.actions else None

        emergency = bool(next_action in PUSH_ACTIONS and owner.stamina < 5 and helper.stamina >= self.RELAY_READY_STAMINA)
        at_planned_point = bool(
            relay is not None
            and relay.owner == hero_id
            and route.expected_chest == relay.handoff_chest
            and helper.position == relay.stage_target
            and helper.stamina >= self.RELAY_READY_STAMINA
        )
        strong_reserve_takeover = bool(
            next_action in PUSH_ACTIONS
            and owner.stamina <= 7
            and helper.stamina >= max(self.RELAY_READY_STAMINA, owner.stamina + 10)
        )
        if not (emergency or at_planned_point or strong_reserve_takeover):
            return False
        if not self._handoff_allowed_by_hysteresis(
            state, hero_id, helper_id, emergency=emergency
        ):
            return False

        takeover = self._other_takeover_plan(state, route)
        if takeover is None:
            return False
        # Un relais n'a de sens que si le nouveau plan ne commence pas par une longue
        # attente de stamina. On accepte l'urgence meme avec une petite recuperation.
        helper_recovery = self._recovery_ticks(takeover.plan.stamina_cost, helper.stamina)
        owner_recovery = self._recovery_ticks(route.remaining_stamina, owner.stamina)
        if not emergency and helper_recovery > max(8, owner_recovery):
            return False

        if at_planned_point:
            reason = relay.reason if relay is not None else "point de relais atteint"
        elif emergency:
            reason = "pousseur sans assez de stamina pour le prochain PUSH"
        else:
            reason = "autre heros dispose d'une reserve nettement superieure"
        return self._perform_handoff(state, hero_id, route, takeover, reason=reason)

    def _route_action(self, state: GameState, hero_id: HeroId, route: _DirectRoute) -> HeroAction:
        action = super()._route_action(state, hero_id, route)
        if action in PUSH_ACTIONS:
            self._pushes_since_handoff[hero_id] = self._pushes_since_handoff.get(hero_id, 0) + 1
        return action

    def _prune_routes(self, state: GameState) -> None:
        super()._prune_routes(state)
        if self._relay is not None and self._relay.owner not in self._direct_routes:
            self._relay = None

    def _direct_collaborative_actions(self, state: GameState) -> dict[HeroId, HeroAction] | None:
        """Version v8 avec planification du relais avant mutation predictive de route."""
        self._prune_chest_targets(state)
        self._prune_routes(state)

        if self._direct_routes:
            for hero_id, route in tuple(self._direct_routes.items()):
                if self._route_valid(state, hero_id, route):
                    self._maybe_handoff(state, hero_id, route)
            self._prune_routes(state)
            # IMPORTANT: construire/stabiliser le point de relais tant que state et
            # route.expected_* decrivent le meme instant.
            self._ensure_relay(state)

            decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
            assigned: set[Position] = set()
            for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
                route = self._direct_routes.get(hero_id)
                if route is None or not self._route_valid(state, hero_id, route):
                    continue
                assigned.add(route.expected_chest)
                decisions[hero_id] = self._route_action(state, hero_id, route)
                self.last_decisions[hero_id.value] = (
                    f"coffre direct cache ({route.plan.chest.row},{route.plan.chest.col}) "
                    f"-> ({route.plan.bush.row},{route.plan.bush.col})"
                )
            if assigned:
                return self._fill_direct_support(state, decisions, assigned)

        plans = self._best_direct_by_hero_chest(state)
        if not plans:
            self._relay = None
            return None
        distinct_chests = {chest for _, chest in plans}
        pair = self._choose_direct_pair(state, plans) if len(distinct_chests) >= 2 else None
        chosen: list[DirectChestPlan] = []
        if pair is not None:
            chosen.extend(pair)
        else:
            best = self._choose_single_direct(state, plans)
            if best is not None:
                chosen.append(best)
        if not chosen:
            self._relay = None
            return None

        self._direct_routes.clear()
        self._relay = None
        decisions = {HeroId.IKOTOFOSA: HeroAction.WAIT, HeroId.IMAHAKI: HeroAction.WAIT}
        assigned: set[Position] = set()
        for plan in chosen:
            self._cache_route(state, plan)
            self._hero_chest_targets[plan.hero_id] = plan.chest
            assigned.add(plan.chest)

        # Un relais n'est cree que pour UNE route. Avec deux coffres distincts,
        # chacun garde son coffre et les PUSH paralleles v8 restent permis.
        self._ensure_relay(state)
        for plan in chosen:
            route = self._direct_routes[plan.hero_id]
            decisions[plan.hero_id] = self._route_action(state, plan.hero_id, route)
            self.last_decisions[plan.hero_id.value] = (
                f"coffre direct ({plan.chest.row},{plan.chest.col}) -> "
                f"cachette ({plan.bush.row},{plan.bush.col}), cout stamina {plan.plan.stamina_cost}"
            )
        self._target_chest = chosen[0].chest
        return self._fill_direct_support(state, decisions, assigned)

    # ------------------------------------------------------------------
    # Idle/support policy
    # ------------------------------------------------------------------

    def _fill_direct_support(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        assigned: set[Position],
    ) -> dict[HeroId, HeroAction]:
        active_owners = set(self._direct_routes)
        # Le relais est calcule AVANT que _route_action n'avance son etat predit.
        # Ici state represente encore le tick courant alors que route.expected_* peut
        # deja representer le tick suivant; on reutilise donc la reservation preparee.
        relay = self._relay
        reserved: set[Position | str] = set()

        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if hero_id in active_owners:
                route = self._direct_routes[hero_id]
                if decisions[hero_id] == HeroAction.WAIT:
                    next_action = route.actions[0] if route.actions else None
                    if next_action in PUSH_ACTIONS and state.heroes[hero_id].stamina < 5:
                        self.last_decisions[hero_id.value] = (
                            f"recharger stamina pour prochain {next_action.value} "
                            f"du coffre ({route.expected_chest.row},{route.expected_chest.col})"
                        )
                continue
            if decisions[hero_id] != HeroAction.WAIT:
                continue

            hero = state.heroes[hero_id]

            # Un specialiste libere par un relais peut partir sur le coffre suivant.
            # Cette priorite est memorisee au moment du handoff, pas recalculee ici.
            if state.elapsed <= self._specialist_priority_until.get(hero_id, -1):
                unlock = self._secondary_unlock_action(
                    state, hero_id, excluded_chests=assigned
                )
                if unlock is not None:
                    action, desc = unlock
                    decisions[hero_id] = action
                    self.last_decisions[hero_id.value] = desc
                    continue
                self._specialist_priority_until.pop(hero_id, None)

            # Un helper de relais ne pousse pas. Il rejoint le point prevu, puis WAIT
            # pour arriver avec une reserve de stamina quand le coffre atteint la zone.
            if relay is not None and relay.helper == hero_id:
                decisions[hero_id] = self._relay_support_action(state, relay)
                continue

            if hero.is_hacking:
                continue

            # Sinon on conserve le comportement v8: pierres (y compris machines
            # porteuses) puis deblocage secondaire.
            action, key, desc = self._best_stone_action_for_hero(
                state, hero_id, reserved=reserved
            )
            if key is not None:
                decisions[hero_id] = action
                reserved.add(key)
                self.last_decisions[hero_id.value] = desc
                continue
            unlock = self._secondary_unlock_action(
                state, hero_id, excluded_chests=assigned
            )
            if unlock is not None:
                action, desc = unlock
                decisions[hero_id] = action
                self.last_decisions[hero_id.value] = desc
                continue
            self.last_decisions[hero_id.value] = desc
        return decisions
