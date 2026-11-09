from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from dependencies.services import get_interaction_service
from dependencies.visitor import RequiredVisitorIdDep
from domain.schemas.errors import ErrorResponse
from domain.schemas.interactions import InteractionToggle, InteractionToggleResponse
from services.interaction import InteractionService

router = APIRouter(prefix="/api/v1", tags=["Interações"])
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]


@router.post(
    "/reviews/{review_id}/interactions",
    response_model=InteractionToggleResponse,
    summary="Alternar interação em avaliação",
    description=(
        "Marca ou desmarca (toggle) um voto like, spoiler ou well_argued do "
        "visitante na avaliação. O primeiro envio marca e o segundo desmarca. "
        "Cada tipo é independente, no máximo 1 de cada por visitante. Retorna "
        "os contadores atualizados. Exige o header X-Visitor-Id."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "X-Visitor-Id ausente"},
        404: {"model": ErrorResponse, "description": "Avaliação não encontrada"},
        422: {"model": ErrorResponse, "description": "Tipo de interação inválido"},
    },
)
def toggle_interaction(
    review_id: Annotated[UUID, Path(description="UUID da avaliação.")],
    payload: InteractionToggle,
    service: InteractionServiceDep,
    visitor_id: RequiredVisitorIdDep,
) -> InteractionToggleResponse:
    return service.toggle(review_id, payload, visitor_id)
