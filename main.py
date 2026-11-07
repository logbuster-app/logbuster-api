import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from config import settings
from controllers.interaction import router as interaction_router
from controllers.review import router as review_router
from domain.errors.movies import DuplicateReviewError, ReviewNotFoundError
from domain.schemas.movies import ErrorResponse
from utils.database import DatabaseConfigurationError

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.setLevel(settings.log_level)
    logger.info("Logbuster API iniciada (%s). Swagger: /api/docs", settings.app_env)
    yield


app = FastAPI(
    title="Logbuster API",
    version="0.1.0",
    description=(
        "API de avaliações e eventos de interação com filmes. "
        "user_id é informado pelo cliente e ainda não constitui autenticação."
    ),
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
    swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
    lifespan=lifespan,
    responses={
        500: {"model": ErrorResponse, "description": "Erro interno"},
        503: {"model": ErrorResponse, "description": "Persistência indisponível"},
    },
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=600,
)
app.include_router(review_router)
app.include_router(interaction_router)


@app.exception_handler(DuplicateReviewError)
async def duplicate_review_handler(
    _request: Request, exc: DuplicateReviewError
) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ReviewNotFoundError)
async def review_not_found_handler(
    _request: Request, exc: ReviewNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DatabaseConfigurationError)
@app.exception_handler(OperationalError)
async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Persistência indisponível (%s).", type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Persistência temporariamente indisponível."},
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Mensagens SQL, parâmetros, payloads e credenciais não entram no log.
    logger.error("Falha interna (%s).", type(exc).__name__)
    return JSONResponse(
        status_code=500, content={"detail": "Erro interno do servidor."}
    )
