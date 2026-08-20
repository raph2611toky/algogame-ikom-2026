from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import HeroAction, HeroId
from app.domain.models import GameState, Position
from app.engine.strategy_v4 import DirectChestPlan, MachineTask
from app.engine.strategy_v10 import OpportunityCommittedPortfolioStrategy


@dataclass(frozen=True, slots=True)
class _IndependentTask:
    chest: Position
    task: MachineTask
    role_exclusive: bool
    shared_support: int


class ProgressiveParallelPortfolioStrategy(OpportunityCommittedPortfolioStrategy):
    """portfolio_v11 corrige = coeur v10 + allocation parallele par roles.

    Principe strict: v10 reste le moteur. V11 n'ajoute aucune nouvelle route de
    coffre, aucun nouveau planner machine et ne remplace ni l'opportunity scheduler,
    ni la protection X/G, ni les micro-plans, ni le relais stamina v9.

    V11 intervient seulement lorsqu'une independance est *deja prouvee* par les
    planners v10:

    - un coffre est direct/libre et peut etre pris par F ou M;
    - un AUTRE coffre possede maintenant une tache machine executable par le heros
      libere (trou pour F, arbre pour M);
    - alors on peut choisir comme pousseur celui qui laisse le specialiste utile
      travailler sur l'autre coffre en parallele;
    - pendant une route directe, le heros sans route prefere une vraie tache coffre
      independante a une pierre secondaire, mais seulement si cela ne casse pas un
      besoin de relais stamina.

    Un simple staging lointain n'est jamais lance par cette couche. C'etait la cause
    principale des regressions de l'ancien v11: le heros partait tres loin pour une
    hypothese de futur travail et n'etait plus disponible au bon moment.
    """

    # On accepte un leger trajet direct plus long si cela libere simultanement une
    # competence qui peut retirer un obstacle MAINTENANT sur un autre coffre.
    MAX_ROLE_DIRECT_SLOWDOWN_TICKS = 18
    MIN_DIRECT_RUNTIME_FOR_ROLE_REALLOCATION = 20
    # Un helper explicitement reserve par v8/v9 pour le handoff n'est pas detourne,
    # sauf s'il est deja engage dans son micro-plan v10 (qui reste souverain).
    MIN_LONG_ROUTE_FOR_PARALLEL_SCAN = 12

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._independent_negative_cache: set[tuple[object, ...]] = set()

    @staticmethod
    def _is_stone_decision(description: str) -> bool:
        text = description.lower()
        return "pierre" in text or "stone" in text or "machine_stones" in text

    def _independent_cache_key(
        self,
        state: GameState,
        hero_id: HeroId,
        excluded_chests: set[Position],
    ) -> tuple[object, ...]:
        # Pas de position du heros: un simple pas ne doit pas relancer une analyse
        # structurelle couteuse. Un mouvement/rotation de machine ou un changement
        # terrain/coffre invalide naturellement la cle.
        return (
            hero_id.value,
            tuple(sorted((p.row, p.col) for p in excluded_chests)),
            tuple(sorted((p.row, p.col) for p in state.holes)),
            tuple(sorted((p.row, p.col) for p in state.trees)),
            tuple(sorted((p.row, p.col) for p in state.chests if p not in excluded_chests)),
            tuple(
                sorted(
                    (
                        m.id,
                        m.position.row,
                        m.position.col,
                        m.orientation.value,
                        str(m.hacked_by.value if m.hacked_by else ""),
                        bool(m.pending_move),
                    )
                    for m in state.machines.values()
                )
            ),
        )

    def _best_independent_task(
        self,
        state: GameState,
        hero_id: HeroId,
        *,
        excluded_chests: set[Position],
    ) -> _IndependentTask | None:
        """Retourne uniquement une tache qui ENLEVE un obstacle maintenant.

        Aucun staging ici. Si v10 ne peut pas produire une MachineTask concrete,
        v11 considere que le travail n'est pas assez certain pour detourner le heros.
        """
        if hero_id in self._defense_intercepts:
            return None
        if not any(chest not in excluded_chests for chest in state.chests):
            return None

        # Un commitment deja engage est gere par v10 lui-meme; ne pas lancer une
        # deuxieme analyse concurrente.
        if hero_id in self._machine_commitments:
            return None

        key = self._independent_cache_key(state, hero_id, excluded_chests)
        if key in self._independent_negative_cache:
            return None

        self._refresh_opportunity_cache(state)
        profiles = self._viable_profiles(state)
        candidates: list[tuple[tuple[object, ...], _IndependentTask]] = []

        for chest, profile in profiles.items():
            if chest in excluded_chests:
                continue
            holes, trees = self._current_obstacle_sets(state, profile)
            if not holes and not trees:
                # Deja direct: le planner direct v8/v10 s'en chargera.
                continue
            own = set(holes if hero_id == HeroId.IKOTOFOSA else trees)
            other = set(trees if hero_id == HeroId.IKOTOFOSA else holes)
            if not own:
                continue

            tasks = self._machine_tasks_for(state, hero_id, own)
            if not tasks:
                continue
            task = tasks[0]
            support = int(self._obstacle_support_cache.get(task.obstacle, 1))
            exclusive = not other
            # Une tache sur corridor partage / competence exclusive est prioritaire;
            # ensuite seulement viennent temps et cout reel calcules par v10.
            rank = (
                -support,
                0 if exclusive else 1,
                task.total_ticks,
                task.total_cost_units,
                chest.row,
                chest.col,
                task.machine_id,
            )
            candidates.append(
                (
                    rank,
                    _IndependentTask(
                        chest=chest,
                        task=task,
                        role_exclusive=exclusive,
                        shared_support=support,
                    ),
                )
            )

        if not candidates:
            self._independent_negative_cache.add(key)
            if len(self._independent_negative_cache) > 256:
                self._independent_negative_cache.clear()
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    # ------------------------------------------------------------------
    # Allocation par roles au moment ou UN coffre direct apparait.
    # ------------------------------------------------------------------

    def _choose_single_direct(
        self,
        state: GameState,
        plans: dict[tuple[HeroId, Position], DirectChestPlan],
    ) -> DirectChestPlan | None:
        base = super()._choose_single_direct(state, plans)
        if base is None or len(state.chests) <= 1:
            return base

        distinct = {plan.chest for plan in plans.values()}
        if len(distinct) != 1:
            return base
        direct_chest = next(iter(distinct))

        by_hero: dict[HeroId, DirectChestPlan] = {}
        for plan in plans.values():
            previous = by_hero.get(plan.hero_id)
            if previous is None or self._plan_runtime_key(state, plan) < self._plan_runtime_key(state, previous):
                by_hero[plan.hero_id] = plan
        if len(by_hero) != 2:
            return base

        base_runtime = int(self._plan_runtime_key(state, base)[0])
        if base_runtime < self.MIN_DIRECT_RUNTIME_FOR_ROLE_REALLOCATION:
            return base
        alternatives: list[tuple[tuple[object, ...], DirectChestPlan]] = []
        for owner_id, plan in by_hero.items():
            helper_id = self._other(owner_id)
            independent = self._best_independent_task(
                state,
                helper_id,
                excluded_chests={direct_chest},
            )
            if independent is None:
                continue
            runtime = int(self._plan_runtime_key(state, plan)[0])
            slowdown = max(0, runtime - base_runtime)
            # Ne pas sacrifier un trajet de coffre enormement plus court pour une
            # simple parallelisation. Le score/relais v10 reste prioritaire.
            if slowdown > self.MAX_ROLE_DIRECT_SLOWDOWN_TICKS and independent.shared_support < 2:
                continue
            rank = (
                max(runtime, independent.task.total_ticks),
                slowdown,
                -independent.shared_support,
                0 if independent.role_exclusive else 1,
                independent.task.total_ticks,
                runtime,
                owner_id.value,
            )
            alternatives.append((rank, plan))

        if not alternatives:
            return base
        alternatives.sort(key=lambda item: item[0])
        chosen = alternatives[0][1]
        chosen_runtime = int(self._plan_runtime_key(state, chosen)[0])

        # Si le bundle parallele ne gagne rien face au choix v10, conserver v10.
        helper_task = self._best_independent_task(
            state,
            self._other(chosen.hero_id),
            excluded_chests={direct_chest},
        )
        if helper_task is None:
            return base
        bundle_finish = max(chosen_runtime, helper_task.task.total_ticks)
        # Le travail independant retire un obstacle reel; on accepte au plus le
        # ralentissement borne ci-dessus. Sinon le choix de base reste intact.
        if bundle_finish > base_runtime + self.MAX_ROLE_DIRECT_SLOWDOWN_TICKS and helper_task.shared_support < 2:
            return base
        return chosen

    # ------------------------------------------------------------------
    # Pendant un coffre direct: faire avancer un autre coffre si c'est sur.
    # ------------------------------------------------------------------

    def _fill_direct_support(
        self,
        state: GameState,
        decisions: dict[HeroId, HeroAction],
        assigned: set[Position],
    ) -> dict[HeroId, HeroAction]:
        decisions = super()._fill_direct_support(state, decisions, assigned)
        active_owners = set(self._direct_routes)
        if not active_owners:
            return decisions

        support_id = self._needs_stamina_support(state, assigned)
        # Les routes courtes ne justifient pas un nouveau scan machine couteux:
        # v10 finira le coffre avant que l'autre tache devienne utile.
        longest_route = max((len(route.actions) for route in self._direct_routes.values()), default=0)
        if longest_route < self.MIN_LONG_ROUTE_FOR_PARALLEL_SCAN:
            return decisions

        for hero_id in (HeroId.IKOTOFOSA, HeroId.IMAHAKI):
            if hero_id in active_owners or hero_id in self._defense_intercepts:
                continue
            current = decisions.get(hero_id, HeroAction.WAIT)
            desc = self.last_decisions.get(hero_id.value, "")
            if current != HeroAction.WAIT and not self._is_stone_decision(desc):
                continue

            # Si v8/v9 a explicitement reserve ce heros pour un relais, on respecte
            # cette decision. C'est precisement ce qui evitera les regressions v11.
            if support_id == hero_id:
                continue

            work = self._best_independent_task(
                state,
                hero_id,
                excluded_chests=set(assigned),
            )
            if work is None:
                continue
            action = self._action_for_machine_task(state, work.task)
            decisions[hero_id] = action
            label = "remplir trou" if hero_id == HeroId.IKOTOFOSA else "couper arbre"
            self.last_decisions[hero_id.value] = (
                f"travail simultane: coffre ({work.chest.row},{work.chest.col}), "
                f"{label} ({work.task.obstacle.row},{work.task.obstacle.col})"
            )
        return decisions

    # ------------------------------------------------------------------
    # Deblocage d'un coffre: v10 reste volontairement INTACT.
    #
    # Une attente apparente pendant un deblocage peut etre une reservation de
    # machine, une future dependance du meme coffre ou une protection X/G. La
    # parallelisation v11 ne s'applique donc qu'entre objectifs independants
    # lorsqu'un coffre direct est deja engage.
    # ------------------------------------------------------------------



# Compatibilite avec simulation_service des versions precedentes.
StrictPriorityPortfolioStrategy = ProgressiveParallelPortfolioStrategy
