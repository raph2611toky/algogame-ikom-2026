from fastapi import APIRouter

from app.core.config import settings
from app.domain.enums import HeroAction
from app.schemas.contracts import AIProfile, ContractsResponse


router = APIRouter(tags=["contracts"])


def _profiles() -> list[AIProfile]:
    return [
        AIProfile(
            name="easy",
            behavior="WAIT ou déplacement légal pseudo-aléatoire, reproductible par seed.",
            information="Aucune position cachée utilisée.",
        ),
        AIProfile(
            name="medium",
            behavior="Vue > dernière position > bruit ; A* court puis patrouille lisible.",
            information="Uniquement perception et mémoire du gardien.",
        ),
        AIProfile(
            name="hard",
            behavior="A*, sélection de cible et carte probabiliste des positions possibles.",
            information="Information partielle stricte : aucune lecture d'un héros invisible.",
        ),
    ]


@router.get("/contracts", response_model=ContractsResponse)
def contracts() -> ContractsResponse:
    return ContractsResponse(
        backend_authoritative=True,
        tick_ms=settings.tick_ms,
        map_header="H W TIME_LIMIT_SECONDS",
        symbols={
            ".": "vide",
            "F": "Ikotofosa",
            "M": "Imahaki",
            "K": "gardien",
            "#": "rocher",
            "t": "arbre",
            "o": "trou",
            "X": "excavateur",
            "G": "grappler",
            "*": "coffre",
            "+": "pierre/charge",
            "@": "cachette",
            "E": "sortie optionnelle recommandée",
        },
        actions=[action.value for action in HeroAction],
        ai_profiles=_profiles(),
        recommendations=[
            "Ticks numérotés et idempotents pour éviter les doubles actions réseau.",
            "Intention du gardien exposée pour une télégraphie visuelle équitable.",
            "Fenêtre de secours KO de 8 s, configurable dans balance.",
        ],
    )


@router.get("/ai/profiles", response_model=list[AIProfile])
def ai_profiles() -> list[AIProfile]:
    return _profiles()
