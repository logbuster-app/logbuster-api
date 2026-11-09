"""Handlers globais que convertem toda falha no envelope da SPEC-API-00."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from domain.errors.base import AppError
from utils.database import DatabaseConfigurationError

logger = logging.getLogger("uvicorn.error")

# Mensagem em português para o primeiro campo inválido (SPEC-API-00, §4.3).
FIELD_MESSAGES = {
    "movie_id": "O movie_id deve ser um imdbID válido (ex.: tt0133093).",
    "review_id": "O review_id deve ser um UUID válido.",
    "type": "O tipo de interação deve ser like, spoiler ou well_argued.",
    "author_name": "O nome do autor deve ter entre 2 e 50 caracteres.",
    "rating": "A nota deve estar entre 0.5 e 5.0 em passos de 0.5.",
    "content": "A descrição deve ter entre 10 e 2000 caracteres.",
    "is_spoiler": "O campo is_spoiler deve ser verdadeiro ou falso.",
    "highlights": (
        "Informe no máximo 2 destaques únicos entre: soundtrack, cinematography, "
        "screenplay, acting, direction e visual_effects."
    ),
}
DEFAULT_VALIDATION_MESSAGE = "Os dados enviados são inválidos."
DEFAULT_BAD_REQUEST_MESSAGE = "Parâmetros da requisição inválidos."

# Parâmetros de query e headers inválidos são 400; corpo e path, 422.
BAD_REQUEST_LOCATIONS = {"query", "header"}

HTTP_CODES = {
    400: ("BAD_REQUEST", "Requisição inválida."),
    404: ("NOT_FOUND", "Recurso não encontrado."),
    405: ("METHOD_NOT_ALLOWED", "Método não permitido."),
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or []}},
        headers=headers,
    )


def _validation_details(errors: list[dict[str, Any]]) -> list[dict[str, str]]:
    details = []
    for error in errors:
        location = [str(part) for part in error.get("loc", ())]
        field = ".".join(location[1:]) or (location[0] if location else "request")
        details.append({"field": field, "issue": str(error.get("msg", ""))})
    return details


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = list(exc.errors())
    first_location = errors[0].get("loc", ()) if errors else ()
    if first_location and first_location[0] in BAD_REQUEST_LOCATIONS:
        status_code, code, message = 400, "BAD_REQUEST", DEFAULT_BAD_REQUEST_MESSAGE
    else:
        status_code, code = 422, "VALIDATION_ERROR"
        field = str(first_location[1]) if len(first_location) > 1 else ""
        message = FIELD_MESSAGES.get(field, DEFAULT_VALIDATION_MESSAGE)
    return error_response(status_code, code, message, _validation_details(errors))


async def http_error_handler(
    _request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # Erros de negócio usam AppError; aqui chegam só os do roteamento do
    # Starlette ("Not Found", "Method Not Allowed"), traduzidos para português.
    code, message = HTTP_CODES.get(
        exc.status_code, ("HTTP_ERROR", "Falha na requisição.")
    )
    return error_response(
        exc.status_code, code, message, headers=getattr(exc, "headers", None)
    )


async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.error("Persistência indisponível (%s).", type(exc).__name__)
    return error_response(
        503, "SERVICE_UNAVAILABLE", "Persistência temporariamente indisponível."
    )


async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Mensagens SQL, parâmetros, payloads e credenciais não entram no log.
    logger.error("Falha interna (%s).", type(exc).__name__)
    return error_response(500, "INTERNAL_ERROR", "Erro interno do servidor.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(DatabaseConfigurationError, database_error_handler)
    app.add_exception_handler(OperationalError, database_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
