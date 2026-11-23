import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from controllers.ai import router as ai_router
from controllers.interaction import router as interaction_router
from controllers.movies import router as movies_router
from controllers.review import router as review_router
from controllers.users import router as users_router
from dependencies.services import shutdown_spoiler_scheduler
from dependencies.visitor import VISITOR_HEADER
from domain.schemas.errors import ErrorResponse
from utils.error_handlers import register_error_handlers

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.setLevel(settings.log_level)
    logger.info("Logbuster API iniciada (%s). Swagger: /api/docs", settings.app_env)
    yield
    shutdown_spoiler_scheduler()


app = FastAPI(
    title="Logbuster API",
    version="0.1.0",
    description=(
        "API de avaliações de filmes do LogBuster. "
        "Publicar avaliações exige conta. Visitantes usam X-Visitor-Id para votar. "
        "Erros seguem o envelope {error: {code, message, details}}."
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
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", VISITOR_HEADER],
    max_age=600,
)
app.include_router(movies_router)
app.include_router(review_router)
app.include_router(interaction_router)
app.include_router(users_router)
app.include_router(ai_router)
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
