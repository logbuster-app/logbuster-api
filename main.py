import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from controllers.review import router as review_router
from domain.schemas.errors import ErrorResponse
from utils.error_handlers import register_error_handlers

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
        "API de avaliações de filmes do LogBuster. Sem login na entrega parcial: "
        "o autor informa author_name e o visitante é identificado pelo header "
        "X-Visitor-Id. Erros seguem o envelope {error: {code, message, details}}."
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
register_error_handlers(app)
