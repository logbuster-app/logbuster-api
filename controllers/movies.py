from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from dependencies.session import get_session
from domain.enums import Highlight
from domain.schemas.errors import ErrorResponse
from domain.schemas.movies import HighlightedMovie, HighlightedMoviesResponse
from repositories.review import ReviewRepository
from services.omdb import (
    MovieNotFound,
    OmdbClient,
    OmdbError,
    TooManyResults,
    get_movie_metadata,
)

router = APIRouter(prefix="/api/v1", tags=["Filmes"])


@lru_cache(maxsize=1)
def get_omdb_client() -> OmdbClient:
    return OmdbClient()


@router.get("/movies")
def search_movies(
    q: Annotated[str, Query(min_length=1)],
    session: Annotated[Session, Depends(get_session)],
    omdb: Annotated[OmdbClient, Depends(get_omdb_client)],
    page: Annotated[int, Query(ge=1)] = 1,
):
    query = q.strip()
    if not query:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "q"),
                    "msg": "Busca vazia",
                    "input": q,
                }
            ]
        )
    try:
        movies, total = omdb.search(query, page)
    except TooManyResults:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Muitos resultados. Digite um termo de busca mais específico.",
                    "details": [],
                }
            },
        )
    except OmdbError:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": "Serviço de filmes indisponível.",
                    "details": [],
                }
            },
        )
    ratings = ReviewRepository(session).ratings_map([movie["id"] for movie in movies])
    for movie in movies:
        movie["rating_avg"], movie["rating_count"] = ratings.get(movie["id"], (None, 0))
    return {"items": movies, "total": total, "page": page, "page_size": 10}


@router.get(
    "/highlights/{highlight}/movies",
    summary="Listar filmes por destaque",
    responses={422: {"model": ErrorResponse, "description": "Dados inválidos"}},
)
def list_highlight_movies(
    highlight: Highlight,
    session: Annotated[Session, Depends(get_session)],
    omdb: Annotated[OmdbClient, Depends(get_omdb_client)],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> HighlightedMoviesResponse:
    ranking = ReviewRepository(session).movies_by_highlight(highlight, limit=limit)
    items = []
    for movie_id, rating_avg, rating_count, count in ranking:
        try:
            title, year, poster_url = get_movie_metadata(omdb, movie_id)
        except (MovieNotFound, OmdbError):
            title, year, poster_url = movie_id, None, None
        items.append(
            HighlightedMovie(
                id=movie_id,
                title=title,
                year=year,
                poster_url=poster_url,
                rating_avg=rating_avg,
                rating_count=rating_count,
                highlight_count=count,
            )
        )
    return HighlightedMoviesResponse(items=items)


@router.get("/movies/{movie_id}")
def get_movie(
    movie_id: Annotated[str, Path(pattern=r"^tt[0-9]{7,10}$")],
    session: Annotated[Session, Depends(get_session)],
    omdb: Annotated[OmdbClient, Depends(get_omdb_client)],
):
    try:
        movie = omdb.get_movie(movie_id)
    except MovieNotFound:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Filme não encontrado.",
                    "details": [],
                }
            },
        )
    except OmdbError:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": "Serviço de filmes indisponível.",
                    "details": [],
                }
            },
        )
    ratings = ReviewRepository(session).ratings_map([movie_id])
    movie["rating_avg"], movie["rating_count"] = ratings.get(movie_id, (None, 0))
    return movie
