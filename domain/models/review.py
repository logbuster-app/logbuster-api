from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base
from utils.db_types import StringList, UTCDateTime


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "movie_id LIKE 'tt%' AND length(movie_id) BETWEEN 9 AND 12 "
            "AND substr(movie_id, 3) NOT GLOB '*[^0-9]*'",
            name="ck_reviews_movie_id",
        ),
        CheckConstraint(
            "length(trim(author_name)) BETWEEN 2 AND 50", name="ck_reviews_author_name"
        ),
        CheckConstraint(
            "rating >= 0.5 AND rating <= 5.0 AND rating * 2 = floor(rating * 2)",
            name="ck_reviews_rating",
        ),
        CheckConstraint(
            "length(trim(content)) BETWEEN 10 AND 2000", name="ck_reviews_content"
        ),
        CheckConstraint(
            "json_array_length(highlights) <= 2", name="ck_reviews_highlights"
        ),
        Index("ix_reviews_movie_created_id", "movie_id", "created_at", "id"),
        Index("ix_reviews_user_created_id", "user_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    movie_id: Mapped[str] = mapped_column(String(12), nullable=False)
    author_name: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), nullable=False)
    content: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_spoiler: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    highlights: Mapped[list[str]] = mapped_column(
        StringList, nullable=False, default=list, server_default=text("'[]'")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_reviews_user_id"),
    )
