from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import ColumnElement, Label, Select, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.enums import ReviewInteractionType, ReviewSort
from domain.models.review import Review
from domain.models.review_interaction import ReviewInteraction


class ReviewWithCounts(NamedTuple):
    review: Review
    like: int
    spoiler: int
    well_argued: int


class _CountColumns(NamedTuple):
    like: Label[int]
    spoiler: Label[int]
    well_argued: Label[int]


def _select_with_counts(
    *review_filter: ColumnElement[bool],
) -> tuple[Select, _CountColumns]:
    """`SELECT reviews.*, <contadores> WHERE <review_filter>`.

    A agregação condicional (`count(*) FILTER (WHERE type = ...)`) conta os três
    tipos numa única passada; o LEFT JOIN mantém avaliações sem votos (contador 0).
    O mesmo filtro é aplicado dentro da subquery para agregar só os votos das
    avaliações consultadas, e não a tabela inteira.
    """

    def count_of(kind: ReviewInteractionType) -> Label[int]:
        return func.count().filter(ReviewInteraction.type == kind).label(kind.value)

    counts = (
        select(
            ReviewInteraction.review_id,
            count_of(ReviewInteractionType.LIKE),
            count_of(ReviewInteractionType.SPOILER),
            count_of(ReviewInteractionType.WELL_ARGUED),
        )
        .join(Review, Review.id == ReviewInteraction.review_id)
        .where(*review_filter)
        .group_by(ReviewInteraction.review_id)
        .subquery("interaction_counts")
    )
    columns = _CountColumns(
        like=func.coalesce(counts.c.like, 0).label("like_count"),
        spoiler=func.coalesce(counts.c.spoiler, 0).label("spoiler_count"),
        well_argued=func.coalesce(counts.c.well_argued, 0).label("well_argued_count"),
    )
    statement = (
        select(Review, *columns)
        .outerjoin(counts, counts.c.review_id == Review.id)
        .where(*review_filter)
    )
    return statement, columns


def _order_by(sort: ReviewSort, counts: _CountColumns) -> list[ColumnElement]:
    """Critérios da SPEC-BACK-02 (RN-01); `id` fecha o desempate de forma estável."""
    newest = [Review.created_at.desc(), Review.id.desc()]
    criteria = {
        ReviewSort.WELL_ARGUED: [counts.well_argued.desc(), counts.like.desc()],
        ReviewSort.MOST_LIKED: [counts.like.desc(), counts.well_argued.desc()],
        ReviewSort.NEWEST: [],
        ReviewSort.RATING_DESC: [Review.rating.desc()],
        ReviewSort.RATING_ASC: [Review.rating.asc()],
    }
    return [*criteria[sort], *newest]


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, review: Review) -> Review:
        try:
            self.session.add(review)
            self.session.flush()
            self.session.refresh(review)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        return review

    def get(self, review_id: UUID) -> Review | None:
        return self.session.get(Review, review_id)

    def get_with_counts(self, review_id: UUID) -> ReviewWithCounts | None:
        statement, _counts = _select_with_counts(Review.id == review_id)
        row = self.session.execute(statement).first()
        return ReviewWithCounts(*row) if row is not None else None

    def list_with_counts(
        self, movie_id: str, *, sort: ReviewSort, limit: int, offset: int
    ) -> list[ReviewWithCounts]:
        statement, counts = _select_with_counts(Review.movie_id == movie_id)
        statement = (
            statement.order_by(*_order_by(sort, counts)).limit(limit).offset(offset)
        )
        return [ReviewWithCounts(*row) for row in self.session.execute(statement)]

    def viewer_interactions(
        self, review_ids: Sequence[UUID], visitor_id: str
    ) -> dict[UUID, list[ReviewInteractionType]]:
        """Tipos já marcados pelo visitante em cada avaliação, numa única query."""
        if not review_ids:
            return {}
        statement = select(ReviewInteraction.review_id, ReviewInteraction.type).where(
            ReviewInteraction.review_id.in_(review_ids),
            ReviewInteraction.visitor_id == visitor_id,
        )
        marked: dict[UUID, list[ReviewInteractionType]] = defaultdict(list)
        for review_id, kind in self.session.execute(statement):
            marked[review_id].append(kind)
        return dict(marked)

    def count(self, movie_id: str) -> int:
        statement = select(func.count(Review.id)).where(Review.movie_id == movie_id)
        return self.session.scalar(statement) or 0

    def rating(self, movie_id: str) -> tuple[Decimal | None, int]:
        statement = select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.movie_id == movie_id
        )
        average, count = self.session.execute(statement).one()
        return average, count
