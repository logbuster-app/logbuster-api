from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from dependencies.services import get_review_service
from dependencies.visitor import OptionalVisitorIdDep
from domain.enums import ReviewSort
from domain.schemas.errors import ErrorResponse
from domain.schemas.movies import IMDB_ID_PATTERN, MovieRating
from domain.schemas.reviews import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
)
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
ImdbMovieId = Annotated[
    str,
    Path(
        pattern=IMDB_ID_PATTERN,
        description="imdbID do filme (ex.: tt0133093).",
        examples=["tt0133093"],
    ),
]
BAD_REQUEST_RESPONSE = {
    400: {"model": ErrorResponse, "description": "Query ou header inválido"}
}


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
    "/movies/{movie_id}/reviews",
    response_model=ReviewListResponse,
    summary="Listar avaliações de um filme",
    description=(
        "Lista paginada com contadores de like, spoiler e well_argued. Por padrão "
        "ordena pelas mais bem argumentadas (well_argued). Filme sem avaliações "
        "retorna 200 com items vazio. Com X-Visitor-Id, viewer_interactions traz "
        "os votos já marcados por aquele visitante."
    ),
    responses=BAD_REQUEST_RESPONSE,
)
def list_reviews(
    movie_id: ImdbMovieId,
    service: ReviewServiceDep,
    visitor_id: OptionalVisitorIdDep,
    sort: Annotated[
        ReviewSort, Query(description="Critério de ordenação.")
    ] = ReviewSort.WELL_ARGUED,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> ReviewListResponse:
    return service.list(
        movie_id, sort=sort, page=page, page_size=page_size, visitor_id=visitor_id
    )


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
