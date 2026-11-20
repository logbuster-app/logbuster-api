from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.exceptions import RequestValidationError

from dependencies.auth import OptionalUserId
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
    ReviewSubmission,
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
        "flag de spoiler e até 2 destaques únicos. Sem autenticação, author_name "
        "é obrigatório. Com um token Bearer válido, a avaliação é vinculada à conta "
        "e usa o nome de exibição do titular."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Token inválido ou expirado"}
    },
    openapi_extra={"security": [{}]},
)
def create_review(
    payload: ReviewSubmission, user_id: OptionalUserId, service: ReviewServiceDep
) -> ReviewResponse:
    if user_id is not None:
        return service.create_for_user(payload, user_id)
    if payload.author_name is None:
        raise RequestValidationError(
            [{"loc": ("body", "author_name"), "msg": "Campo obrigatório sem login."}]
        )
    return service.create(ReviewCreate.model_validate(payload.model_dump()))


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
    "/reviews/{review_id}",
    response_model=ReviewResponse,
    summary="Consultar avaliação",
    description=(
        "Retorna os dados e os contadores atualizados de uma avaliação, no mesmo "
        "formato de item da listagem. Com X-Visitor-Id, viewer_interactions traz "
        "os votos já marcados por aquele visitante."
    ),
    responses={
        **BAD_REQUEST_RESPONSE,
        404: {"model": ErrorResponse, "description": "Avaliação não encontrada"},
    },
)
def get_review(
    review_id: Annotated[UUID, Path(description="UUID da avaliação.")],
    service: ReviewServiceDep,
    visitor_id: OptionalVisitorIdDep,
) -> ReviewResponse:
    return service.get(review_id, visitor_id=visitor_id)


@router.get(
    "/movies/{movie_id}/rating",
    response_model=MovieRating,
    summary="Consultar nota média do filme",
    description=(
        "Média calculada no banco e arredondada a duas casas decimais. "
        "Sem avaliações, retorna rating_avg: null e rating_count: 0."
    ),
)
def get_rating(movie_id: ImdbMovieId, service: ReviewServiceDep) -> MovieRating:
    return service.rating(movie_id)
