from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from domain.enums import ReviewInteractionType
from utils.database import Base
from utils.db_types import UTCDateTime


class ReviewInteraction(Base):
    """Voto de um visitante anônimo em uma avaliação (1 por tipo, SPEC-BACK-06).

    A unique `(review_id, visitor_id, type)` também atende às consultas por
    `review_id`, por ser a coluna líder do índice.
    """

    __tablename__ = "review_interactions"
    __table_args__ = (
        UniqueConstraint(
            "review_id",
            "visitor_id",
            "type",
            name="uq_review_interactions_review_visitor_type",
        ),
        CheckConstraint(
            "length(trim(visitor_id)) > 0", name="ck_review_interactions_visitor_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "reviews.id",
            ondelete="CASCADE",
            name="fk_review_interactions_review_id",
        ),
        nullable=False,
    )
    visitor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[ReviewInteractionType] = mapped_column(
        Enum(
            ReviewInteractionType,
            name="review_interaction_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
