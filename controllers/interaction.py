from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from dependencies.services import get_interaction_service
from domain.schemas.movies import InteractionCreate, InteractionRead
from services.interaction import InteractionService

router = APIRouter(prefix="/api/v1", tags=["Interações"])
InteractionServiceDep = Annotated[InteractionService, Depends(get_interaction_service)]


@router.post(
    "/movies/{movie_id}/interactions",
    response_model=InteractionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar evento de interação",
    description="Cada chamada registra um evento independente, inclusive eventos repetidos.",
)
def create_interaction(
    movie_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    payload: InteractionCreate,
    service: InteractionServiceDep,
) -> InteractionRead:
    return service.create(movie_id, payload)
