from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from pydantic import TypeAdapter

from domain.enums import ReviewInteractionType, ReviewSort
from domain.errors.reviews import ReviewNotFoundError
from domain.errors.users import UnauthorizedError
from domain.models.review import Review
from domain.schemas.movies import Identifier, MovieRating
from domain.schemas.reviews import (
    DEFAULT_PAGE_SIZE,
    ReviewCounts,
    ReviewListQuery,
    ReviewListResponse,
    ReviewResponse,
    ReviewSubmission,
    UserReviewListQuery,
    UserReviewListResponse,
)
from domain.schemas.users import Archetype
from repositories.review import ReviewRepository, ReviewWithCounts
from services.archetype import ReviewFacts, classify
from services.spoiler_scheduler import SpoilerScheduler

_identifier = TypeAdapter(Identifier)


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        spoiler_scheduler: SpoilerScheduler | None = None,
    ) -> None:
        self.repository = repository
        # Sem agendador (ex.: em testes), a avaliação fica como o autor publicou.
        self.spoiler_scheduler = spoiler_scheduler

    def create_for_user(
        self, payload: ReviewSubmission, user_id: UUID
    ) -> ReviewResponse:
        payload = ReviewSubmission.model_validate(payload)
        author = self.repository.get_author(user_id)
        if author is None:
            raise UnauthorizedError()
        review = Review(
            movie_id=payload.movie_id,
            author_name=author.display_name,
            user_id=author.id,
            # Decimal a partir do texto evita ruído binário de float no Numeric.
            rating=Decimal(str(payload.rating)),
            content=payload.content,
            is_spoiler=payload.is_spoiler,
            highlights=[highlight.value for highlight in payload.highlights],
        )
        created = self.repository.create(review)
        # CR-02: depois de salvar, a IA analisa em segundo plano. A resposta não
        # espera, e avaliação já marcada pelo autor não chama a IA (RN-01, RN-03).
        if not created.is_spoiler and self.spoiler_scheduler is not None:
            self.spoiler_scheduler.schedule(created.id)
        # Recém-criada: contadores zerados e nenhum voto do visitante (RN-05).
        return ReviewResponse.from_model(created)

    def list_for_user(
        self, user_id: UUID, query: UserReviewListQuery
    ) -> UserReviewListResponse:
        rows = self.repository.list_for_user(
            user_id, limit=query.page_size, offset=query.offset
        )
        return UserReviewListResponse(
            items=[self._to_response(row, []) for row in rows],
            total=self.repository.count_for_user(user_id),
            page=query.page,
            page_size=query.page_size,
        )

    def archetype(self, user_id: UUID) -> Archetype | None:
        """Recalculado a cada consulta a partir das avaliações da conta."""
        result = classify(
            [
                ReviewFacts(
                    rating=float(row.review.rating),
                    is_spoiler=row.review.is_spoiler,
                    highlights=row.review.highlights,
                    spoiler_votes=row.spoiler,
                    well_argued_votes=row.well_argued,
                )
                for row in self.repository.rows_for_author(user_id)
            ]
        )
        if result is None:
            return None
        return Archetype(title=result.title, description=result.description)

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

    def get(self, review_id: UUID, *, visitor_id: str | None = None) -> ReviewResponse:
        row = self.repository.get_with_counts(review_id)
        if row is None:
            raise ReviewNotFoundError()
        marked = (
            self.repository.viewer_interactions([review_id], visitor_id)
            if visitor_id
            else {}
        )
        return self._to_response(row, marked.get(review_id, []))

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
