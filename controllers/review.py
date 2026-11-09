from typing import Annotated

from fastapi import APIRouter, Depends, Path, status

from dependencies.services import get_review_service
from domain.schemas.errors import ErrorResponse
from domain.schemas.movies import MovieRating
from domain.schemas.reviews import ReviewCreate, ReviewResponse
from services.review import ReviewService

router = APIRouter(
    prefix="/api/v1",
    tags=["Avaliações"],
    responses={
        422: {"model": ErrorResponse, "description": "Dados inválidos"},
    },
)
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
    "/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar avaliação",
    description=(
        "Cria uma avaliação com estrelas de 0.5 a 5.0 (passos de 0.5), descrição, "
        "nome do autor, flag provisória de spoiler e até 2 destaques únicos. "
        "A avaliação nasce com contadores de interação zerados."
    ),
)
def create_review(payload: ReviewCreate, service: ReviewServiceDep) -> ReviewResponse:
    return service.create(payload)


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
