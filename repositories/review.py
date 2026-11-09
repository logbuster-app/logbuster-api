from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.models.review import Review


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

    def count(self, movie_id: str) -> int:
        statement = select(func.count(Review.id)).where(Review.movie_id == movie_id)
        return self.session.scalar(statement) or 0

    def rating(self, movie_id: str) -> tuple[Decimal | None, int]:
        statement = select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.movie_id == movie_id
        )
        average, count = self.session.execute(statement).one()
        return average, count
