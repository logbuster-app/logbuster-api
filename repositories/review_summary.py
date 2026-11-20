from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.models.review_summary import ReviewSummary

LOCK_NAMESPACE = "review-summary:"


class ReviewSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, movie_id: str, *, refresh: bool = False) -> ReviewSummary | None:
        return self.session.get(ReviewSummary, movie_id, populate_existing=refresh)

    def try_lock(self, movie_id: str) -> bool:
        """Trava de transação por filme: uma geração em andamento por vez.

        `pg_try_advisory_xact_lock` não espera; a trava some no commit ou
        rollback, inclusive se o processo cair no meio da geração.
        """
        key = func.hashtextextended(f"{LOCK_NAMESPACE}{movie_id}", 0)
        return bool(self.session.scalar(select(func.pg_try_advisory_xact_lock(key))))

    def release(self) -> None:
        """Encerra a transação sem gravar nada, liberando a trava."""
        self.session.rollback()

    def save_success(
        self,
        movie_id: str,
        *,
        text: str,
        generated_at: datetime,
        reviews_count: int,
        source_review_ids: Sequence[UUID],
    ) -> None:
        self._upsert(
            movie_id,
            text=text,
            generated_at=generated_at,
            reviews_count=reviews_count,
            source_review_ids=list(source_review_ids),
            failed_at=None,
        )

    def save_failure(self, movie_id: str, *, failed_at: datetime) -> None:
        # Mantém o texto anterior no banco, mas o serviço só o serve se ainda
        # for válido; a data de falha apenas espaça novas tentativas.
        self._upsert(movie_id, failed_at=failed_at)

    def _upsert(self, movie_id: str, **values: object) -> None:
        statement = insert(ReviewSummary).values(movie_id=movie_id, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[ReviewSummary.movie_id],
            set_={key: statement.excluded[key] for key in values},
        )
        try:
            self.session.execute(statement)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
