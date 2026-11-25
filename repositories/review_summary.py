import threading
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from domain.models.review_summary import ReviewSummary

_LOCKS_GUARD = threading.Lock()
_ACTIVE_SUMMARY_LOCKS: set[str] = set()


class ReviewSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        self._locked_movie_id: str | None = None

    def get(self, movie_id: str, *, refresh: bool = False) -> ReviewSummary | None:
        return self.session.get(ReviewSummary, movie_id, populate_existing=refresh)

    def try_lock(self, movie_id: str) -> bool:
        """Trava em memória por filme: uma geração em andamento por vez."""
        with _LOCKS_GUARD:
            if movie_id in _ACTIVE_SUMMARY_LOCKS:
                return False
            _ACTIVE_SUMMARY_LOCKS.add(movie_id)
            self._locked_movie_id = movie_id
            return True

    def release(self) -> None:
        """Libera a trava do filme e encerra a transação sem gravar nada."""
        self._release_lock()
        self.session.rollback()

    def _release_lock(self) -> None:
        if self._locked_movie_id is None:
            return
        with _LOCKS_GUARD:
            _ACTIVE_SUMMARY_LOCKS.discard(self._locked_movie_id)
        self._locked_movie_id = None

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
        finally:
            self._release_lock()
