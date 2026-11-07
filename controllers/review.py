from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from dependencies.services import get_review_service
from domain.schemas.movies import (
    ErrorResponse,
    MovieRating,
    ReviewCreate,
    ReviewPage,
    ReviewRead,
)
from services.review import ReviewService

router = APIRouter(prefix="/api/v1", tags=["Avaliações"])
ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
MovieId = Annotated[
    str,
    Path(
        min_length=1,
        max_length=128,
        pattern=r"\S",
        description="Identificador do catálogo, independente de provedor (até 128 caracteres).",
    ),
]


@router.post(
    "/movies/{movie_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar avaliação",
    responses={
        409: {"model": ErrorResponse, "description": "Usuário já avaliou o filme"}
    },
)
def create_review(
    movie_id: MovieId, payload: ReviewCreate, service: ReviewServiceDep
) -> ReviewRead:
    return service.create(movie_id, payload)


@router.get(
    "/movies/{movie_id}/reviews",
    response_model=ReviewPage,
    summary="Listar avaliações de um filme",
)
def list_reviews(
    movie_id: MovieId,
    service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReviewPage:
    return service.list(movie_id, limit=limit, offset=offset)


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Consultar avaliação",
    responses={
        404: {"model": ErrorResponse, "description": "Avaliação não encontrada"}
    },
)
def get_review(review_id: UUID, service: ReviewServiceDep) -> ReviewRead:
    return service.get(review_id)


@router.get(
    "/movies/{movie_id}/rating",
    response_model=MovieRating,
    summary="Consultar nota média do filme",
    description=(
        "Média calculada no banco e arredondada a duas casas decimais. "
        "Sem avaliações, retorna average_rating: null e reviews_count: 0."
    ),
)
def get_rating(movie_id: MovieId, service: ReviewServiceDep) -> MovieRating:
    return service.rating(movie_id)
