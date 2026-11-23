from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from starlette.exceptions import HTTPException as StarletteHTTPException

from dependencies.services import get_review_summary_service
from domain.schemas.ai import ReviewSummaryResponse
from domain.schemas.errors import ErrorResponse
from domain.schemas.movies import IMDB_ID_PATTERN
from services.review_summary import ReviewSummaryService

router = APIRouter(
    prefix="/api/v1",
    tags=["IA"],
    responses={422: {"model": ErrorResponse, "description": "Dados inválidos"}},
)
ReviewSummaryServiceDep = Annotated[
    ReviewSummaryService, Depends(get_review_summary_service)
]


@router.get(
    "/movies/{movie_id}/review-summary",
    response_model=ReviewSummaryResponse,
    summary="Consultar resumo da comunidade",
    description=(
        "Parágrafo gerado por IA sobre a opinião da comunidade, sem spoilers. "
        "Com menos de 3 avaliações retorna insufficient_reviews sem consultar a IA. "
        "Avaliações com is_spoiler (do autor ou da IA) ou com 10 ou mais votos de "
        "spoiler ficam de fora. O texto fica em cache por filme e é regerado após "
        "novas avaliações. Falha, demora ou ausência de texto elegível retornam "
        "200 com status unavailable, sem afetar a ficha do filme."
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


@router.post("/reviews/spoiler-check", include_in_schema=False)
def removed_spoiler_check() -> None:
    """Rota removida pelo CR-02 (§5.4): a análise agora roda após publicar.

    Sem este marcador, o caminho casaria com `GET /reviews/{review_id}` e o
    cliente receberia 405 em vez do 404 exigido pelo CR.
    """
    raise StarletteHTTPException(status_code=status.HTTP_404_NOT_FOUND)
