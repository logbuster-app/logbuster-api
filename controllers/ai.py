from typing import Annotated

from fastapi import APIRouter, Depends, Path

from dependencies.services import (
    get_review_summary_service,
    get_spoiler_check_service,
)
from domain.schemas.ai import ReviewSummaryResponse, SpoilerCheckResponse
from domain.schemas.errors import ErrorResponse
from domain.schemas.movies import IMDB_ID_PATTERN
from domain.schemas.reviews import SpoilerCheckRequest
from services.review_summary import ReviewSummaryService
from services.spoiler import SpoilerCheckService

router = APIRouter(
    prefix="/api/v1",
    tags=["IA"],
    responses={422: {"model": ErrorResponse, "description": "Dados inválidos"}},
)
ReviewSummaryServiceDep = Annotated[
    ReviewSummaryService, Depends(get_review_summary_service)
]
SpoilerCheckServiceDep = Annotated[
    SpoilerCheckService, Depends(get_spoiler_check_service)
]


@router.get(
    "/movies/{movie_id}/review-summary",
    response_model=ReviewSummaryResponse,
    summary="Consultar resumo da comunidade",
    description=(
        "Parágrafo gerado por IA sobre a opinião da comunidade, sem spoilers. "
        "Com menos de 3 avaliações retorna insufficient_reviews sem consultar a IA. "
        "Avaliações marcadas como spoiler ou com 3 votos de spoiler ficam de fora. "
        "O texto fica em cache por filme e é regerado após novas avaliações. "
        "Falha, demora ou ausência de texto elegível retornam 200 com status "
        "unavailable, sem afetar a ficha do filme."
    ),
)
def get_review_summary(
    movie_id: Annotated[
        str,
        Path(
            pattern=IMDB_ID_PATTERN,
            description="imdbID do filme (ex.: tt0133093).",
            examples=["tt0133093"],
        ),
    ],
    service: ReviewSummaryServiceDep,
) -> ReviewSummaryResponse:
    return service.get(movie_id)


@router.post(
    "/reviews/spoiler-check",
    response_model=SpoilerCheckResponse,
    summary="Sugerir marcação de spoiler",
    description=(
        "Analisa o rascunho antes da publicação, inclusive para visitantes sem "
        "login. Só sugere: não cria, altera nem oculta avaliações. suspected deve "
        "acionar o aviso no modal; clear e unavailable publicam sem aviso. A "
        "escolha do autor segue em is_spoiler no POST /api/v1/reviews."
    ),
)
def check_spoiler(
    payload: SpoilerCheckRequest, service: SpoilerCheckServiceDep
) -> SpoilerCheckResponse:
    return SpoilerCheckResponse(status=service.check(payload.movie_id, payload.content))
