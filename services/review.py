from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

from pydantic import TypeAdapter

from domain.enums import ReviewInteractionType, ReviewSort
from domain.models.review import Review
from domain.schemas.movies import Identifier, MovieRating
from domain.schemas.reviews import (
    DEFAULT_PAGE_SIZE,
    ReviewCounts,
    ReviewCreate,
    ReviewListQuery,
    ReviewListResponse,
    ReviewResponse,
)
from repositories.review import ReviewRepository, ReviewWithCounts

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

    def list(
        self,
        movie_id: str,
        *,
        sort: ReviewSort = ReviewSort.WELL_ARGUED,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
        visitor_id: str | None = None,
    ) -> ReviewListResponse:
        query = ReviewListQuery(
            movie_id=movie_id, sort=sort, page=page, page_size=page_size
        )
        rows = self.repository.list_with_counts(
            query.movie_id, sort=query.sort, limit=query.page_size, offset=query.offset
        )
        # Sem X-Visitor-Id (ou sem itens) não há o que consultar (RN-03).
        marked = (
            self.repository.viewer_interactions(
                [row.review.id for row in rows], visitor_id
            )
            if visitor_id and rows
            else {}
        )
        return ReviewListResponse(
            items=[
                self._to_response(row, marked.get(row.review.id, [])) for row in rows
            ],
            # Filme sem avaliações: 200 com items [] e total 0, nunca 404 (RN-02).
            total=self.repository.count(query.movie_id),
            page=query.page,
            page_size=query.page_size,
            sort=query.sort,
        )

    @staticmethod
    def _to_response(
        row: ReviewWithCounts, viewer_interactions: Iterable[ReviewInteractionType]
    ) -> ReviewResponse:
        counts = ReviewCounts(
            like=row.like, spoiler=row.spoiler, well_argued=row.well_argued
        )
        return ReviewResponse.from_model(row.review, counts, viewer_interactions)

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
