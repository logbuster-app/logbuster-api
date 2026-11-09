from domain.errors.base import NotFoundError


class ReviewNotFoundError(NotFoundError):
    message = "Avaliação não encontrada."
