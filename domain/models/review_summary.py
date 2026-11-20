from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, String
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from utils.database import Base


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
            "movie_id ~ '^tt[0-9]{7,10}$'", name="ck_review_summaries_movie_id"
        ),
        CheckConstraint("reviews_count >= 0", name="ck_review_summaries_count"),
    )

    movie_id: Mapped[str] = mapped_column(String(12), primary_key=True)
    text: Mapped[str | None] = mapped_column(String(2000))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviews_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sql_text("0")
    )
    source_review_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PGUUID(as_uuid=True)),
        nullable=False,
        default=list,
        server_default=sql_text("'{}'"),
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
