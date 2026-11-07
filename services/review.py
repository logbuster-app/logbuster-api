from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from pydantic import TypeAdapter

from domain.errors.movies import ReviewNotFoundError
from domain.models.review import Review
from domain.schemas.movies import (
    Identifier,
    MovieRating,
    PaginationParams,
    ReviewCreate,
    ReviewPage,
    ReviewRead,
)
from repositories.review import ReviewRepository

_identifier = TypeAdapter(Identifier)


class ReviewService:
    def __init__(self, repository: ReviewRepository) -> None:
        self.repository = repository

    def create(self, movie_id: str, payload: ReviewCreate) -> ReviewRead:
        movie_id = _identifier.validate_python(movie_id)
        payload = ReviewCreate.model_validate(payload)
        review = Review(movie_id=movie_id, **payload.model_dump())
        return ReviewRead.model_validate(self.repository.create(review))

    def list(self, movie_id: str, *, limit: int = 20, offset: int = 0) -> ReviewPage:
        movie_id = _identifier.validate_python(movie_id)
        params = PaginationParams(limit=limit, offset=offset)
        items = self.repository.list(movie_id, limit=params.limit, offset=params.offset)
        return ReviewPage(
            items=[ReviewRead.model_validate(item) for item in items],
            total=self.repository.count(movie_id),
            limit=params.limit,
            offset=params.offset,
        )

    def get(self, review_id: UUID) -> ReviewRead:
        review = self.repository.get(review_id)
        if review is None:
            raise ReviewNotFoundError()
        return ReviewRead.model_validate(review)

    def rating(self, movie_id: str) -> MovieRating:
        movie_id = _identifier.validate_python(movie_id)
        average, count = self.repository.rating(movie_id)
        rounded = (
            float(
                Decimal(str(average)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
            if count and average is not None
            else None
        )
        return MovieRating(
            movie_id=movie_id, average_rating=rounded, reviews_count=count
        )
