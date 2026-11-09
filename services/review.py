from decimal import ROUND_HALF_UP, Decimal

from pydantic import TypeAdapter

from domain.models.review import Review
from domain.schemas.movies import Identifier, MovieRating
from domain.schemas.reviews import ReviewCreate, ReviewResponse
from repositories.review import ReviewRepository

_identifier = TypeAdapter(Identifier)


class ReviewService:
    def __init__(self, repository: ReviewRepository) -> None:
        self.repository = repository

    def create(self, payload: ReviewCreate) -> ReviewResponse:
        payload = ReviewCreate.model_validate(payload)
        review = Review(
            movie_id=payload.movie_id,
            author_name=payload.author_name,
            # Decimal a partir do texto evita ruído binário de float no Numeric.
            rating=Decimal(str(payload.rating)),
            content=payload.content,
            is_spoiler=payload.is_spoiler,
            highlights=[highlight.value for highlight in payload.highlights],
        )
        # Recém-criada: contadores zerados e nenhum voto do visitante (RN-05).
        return ReviewResponse.from_model(self.repository.create(review))

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
