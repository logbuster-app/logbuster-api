"""Envelope único de erro (SPEC-API-00, §4.3) para falhas fora da validação."""

import pytest
from sqlalchemy.exc import OperationalError

from domain.errors.base import AppError, NotFoundError
from domain.errors.reviews import ReviewNotFoundError
from utils.database import DatabaseConfigurationError

PAYLOAD = {
    "movie_id": "tt0133093",
    "author_name": "Thyago",
    "rating": 4.0,
    "content": "Uma análise longa o bastante.",
}


@pytest.mark.parametrize(
    "error,status,code,message",
    [
        (
            OperationalError("insert", {}, Exception("SENSITIVE")),
            503,
            "SERVICE_UNAVAILABLE",
            "Persistência temporariamente indisponível.",
        ),
        (
            DatabaseConfigurationError("SENSITIVE"),
            503,
            "SERVICE_UNAVAILABLE",
            "Persistência temporariamente indisponível.",
        ),
        (RuntimeError("SENSITIVE"), 500, "INTERNAL_ERROR", "Erro interno do servidor."),
        (ReviewNotFoundError(), 404, "NOT_FOUND", "Avaliação não encontrada."),
        (NotFoundError(), 404, "NOT_FOUND", "Recurso não encontrado."),
        (AppError(), 400, "BAD_REQUEST", "Requisição inválida."),
    ],
)
def test_errors_use_envelope_without_internal_details(
    client, review_service, error, status, code, message, caplog
):
    review_service.create.side_effect = error
    response = client.post("/api/v1/reviews", json=PAYLOAD)
    assert response.status_code == status
    assert response.json() == {
        "error": {"code": code, "message": message, "details": []}
    }
    assert "SENSITIVE" not in response.text
    assert "SENSITIVE" not in caplog.text


def test_app_error_carries_custom_message_and_details(client, review_service):
    review_service.create.side_effect = AppError(
        "Mensagem própria.", [{"field": "x", "issue": "y"}]
    )
    response = client.post("/api/v1/reviews", json=PAYLOAD)
    assert response.json()["error"] == {
        "code": "BAD_REQUEST",
        "message": "Mensagem própria.",
        "details": [{"field": "x", "issue": "y"}],
    }


def test_output_schema_is_enforced(client, review_service):
    review_service.create.return_value = {"id": "invalid"}
    response = client.post("/api/v1/reviews", json=PAYLOAD)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
