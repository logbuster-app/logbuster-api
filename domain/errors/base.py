from typing import Any


class AppError(Exception):
    """Erro de negócio convertido no envelope padrão da SPEC-API-00.

    Cada subclasse define `status_code`, `code` e `message`; o handler global
    monta `{"error": {"code", "message", "details"}}`.
    """

    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "Requisição inválida."

    def __init__(
        self, message: str | None = None, details: list[dict[str, Any]] | None = None
    ) -> None:
        self.message = message or self.message
        self.details = details or []
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Recurso não encontrado."
