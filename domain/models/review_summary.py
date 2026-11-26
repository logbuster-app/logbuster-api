from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base
from utils.db_types import UTCDateTime, UuidList


class ReviewSummary(Base):
    """Último resumo da comunidade gerado por IA para um filme (SPEC-BACK-09).

    `reviews_count` guarda quantas avaliações o filme tinha na geração, para
    medir o limiar de avaliações novas. `source_review_ids` lista as avaliações
    enviadas à IA: se alguma deixar de ser elegível (3 votos de spoiler), o
    texto deixa de ser servido. `failed_at` espaça novas tentativas após falha.
    """

    __tablename__ = "review_summaries"
    __table_args__ = (
        CheckConstraint(
            "movie_id LIKE 'tt%' AND length(movie_id) BETWEEN 9 AND 12 "
            "AND substr(movie_id, 3) NOT GLOB '*[^0-9]*'",
            name="ck_review_summaries_movie_id",
        ),
        CheckConstraint("reviews_count >= 0", name="ck_review_summaries_count"),
    )

    movie_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    text: Mapped[str | None] = mapped_column(String(2000))
    generated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviews_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sql_text("0")
    )
    source_review_ids: Mapped[list[UUID]] = mapped_column(
        UuidList,
        nullable=False,
        default=list,
        server_default=sql_text("'[]'"),
    )
    failed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
