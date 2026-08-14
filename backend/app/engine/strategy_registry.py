from __future__ import annotations

from dataclasses import dataclass, asdict

DEFAULT_STRATEGY = "portfolio_v7"


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    name: str
    label: str
    family: str
    description: str
    recommended: bool = False
    supports_large_maps: bool = True

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


STRATEGIES: tuple[StrategyDescriptor, ...] = (
    StrategyDescriptor(
        "portfolio_v7",
        "Portfolio v7 — collaboratif + cache",
        "portfolio",
        "Version recommandée: conserve les priorités coffres/machines/pierres de v6, évite les recalculs structurels identiques et réduit fortement le coût des décisions répétées.",
        True,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v6",
        "Portfolio v6 — collaboratif optimisé",
        "portfolio",
        "Version précédente, très complète mais plus coûteuse sur les cartes larges ou longues.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v5",
        "Portfolio v5 — collaboratif",
        "portfolio",
        "Version collaborative antérieure, utile pour comparaison de comportement.",
    ),
    StrategyDescriptor(
        "portfolio_v4",
        "Portfolio v4 — coffres prioritaires",
        "portfolio",
        "Priorité forte aux coffres et aux déblocages par machines.",
    ),
    StrategyDescriptor(
        "portfolio_v3",
        "Portfolio v3 — portefeuille historique",
        "portfolio",
        "Compare plusieurs stratégies historiques et conserve le meilleur score local.",
    ),
    StrategyDescriptor(
        "adaptive_v2",
        "Adaptive v2",
        "adaptive",
        "Planification score-aware plus ancienne, utile pour benchmark.",
    ),
    StrategyDescriptor(
        "heuristic_v1",
        "Heuristic v1",
        "baseline",
        "Baseline heuristique rapide pour comparaison.",
    ),
    StrategyDescriptor(
        "scalable_v1",
        "Scalable v1",
        "scalable",
        "Profil borné pour stress tests et grandes cartes; plus rapide mais moins exhaustif sur les coffres complexes.",
        False,
        True,
    ),
)


def strategy_names() -> tuple[str, ...]:
    return tuple(item.name for item in STRATEGIES)


def strategy_catalog() -> list[dict[str, object]]:
    return [item.as_dict() for item in STRATEGIES]
