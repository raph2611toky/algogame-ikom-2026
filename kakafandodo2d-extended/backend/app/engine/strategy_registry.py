from __future__ import annotations

from dataclasses import dataclass, asdict

DEFAULT_STRATEGY = "portfolio_v14"


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
        "portfolio_v14",
        "Portfolio v14 — missions globales + coffres assistes par machines",
        "portfolio",
        "Strategie recommandee: conserve V13/V12 comme filet de securite et ajoute un MachineChestPlanner pour les pushes uphill, allocation conjointe F+M, cout reel temps/stamina/batterie, reserve de stamina non lineaire, poursuite/interception de machines et release securise avant abandon.",
        True,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v13",
        "Portfolio v13 — IA globale predictive + elevation",
        "portfolio",
        "Fallback historique: active V10/V11/V12 sur les cartes d evaluation, raisonne en cout de score reel (temps/stamina/batterie), estime les taches machines avec les vrais planners elevation/look-ahead, predit les risques machines dans le simulateur et compare plusieurs trajectoires completes avant de garder la meilleure.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v12",
        "Portfolio v12 — GDD addendum + elevation + parallelisme",
        "portfolio",
        "Second-week strategy: conserve les fichiers/coeurs v8-v11, utilise le look-ahead officiel dans les relocalisations et anticipe les risques de coffres lies a l elevation/falaises.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v10",
        "Portfolio v10 — opportunites + micro-plans machines",
        "portfolio",
        "Version recommandee: conserve portfolio_v9/v8 et ajoute seulement, pour les coffres bloques, la priorite aux corridors partages, le commitment de micro-plans machines, anti-oscillation/deadlock et collecte parallele du heros non requis.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v11",
        "Portfolio v11 — parallelisme progressif par roles",
        "portfolio",
        "Candidate conserve le coeur v10. Quand un coffre direct est deja traite, le heros libre prefere une vraie tache executable sur un autre coffre a une pierre secondaire; aucune parallelisation n'est lancee si elle casserait un relais stamina ou exige seulement un staging lointain.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v9",
        "Portfolio v9 — coeur v8 + relais minimal",
        "portfolio",
        "Version recommandee: coeur portfolio_v8 strictement conserve; ajout limite a une affinite de pousseur sur le meme coffre, un relais stamina prudent sur le dernier coffre et un staging local uniquement a la place d'un WAIT de reserve v8.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v8",
        "Portfolio v8 — stamina + handoff + score peak",
        "portfolio",
        "Version precedente: collaboration stamina-aware pour les coffres, orientation sure des machines avant UNHACK, cache direct et conservation du meilleur prefixe de score.",
        False,
        True,
    ),
    StrategyDescriptor(
        "portfolio_v7",
        "Portfolio v7 — collaboratif + cache",
        "portfolio",
        "Version precedente: conserve les priorites coffres/machines/pierres de v6 et les caches structurels.",
        False,
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
