class DomainError(Exception):
    """Erro de negócio independente do transporte HTTP."""


class DuplicateReviewError(DomainError):
    def __init__(self) -> None:
        super().__init__("O usuário já avaliou este filme.")


class ReviewNotFoundError(DomainError):
    def __init__(self) -> None:
        super().__init__("Avaliação não encontrada.")
