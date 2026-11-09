from domain.errors.base import AppError, NotFoundError


class ReviewNotFoundError(NotFoundError):
    message = "Avaliação não encontrada."


class MissingVisitorIdError(AppError):
    """Votar exige identificar o visitante anônimo (SPEC-BACK-06, RN-02)."""

    message = "O header X-Visitor-Id é obrigatório para registrar interações."

    def __init__(self) -> None:
        super().__init__(
            details=[{"field": "X-Visitor-Id", "issue": "Header ausente ou vazio."}]
        )
