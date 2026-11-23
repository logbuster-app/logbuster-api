"""Análise de spoiler depois de publicar (CR-02, §5.1).

`ReviewService.create_for_user` salva a avaliação, responde na hora e agenda
a análise aqui. A tarefa roda num pool pequeno de threads, fora da
requisição, com sessão de banco própria (a da requisição já foi encerrada).

Regras:
- A IA só liga: `suspected` grava `is_spoiler = true`; `clear` e
  `unavailable` não mudam nada (RN-02 e RN-05).
- Avaliação já marcada não chama a IA (RN-03).
- Cada análise vai para o log com ID, resultado e se havia sinopse, sem o
  texto (RN-08).
- Erros vão para o log e nunca derrubam o processo. Análises na fila se
  perdem se o processo reiniciar; a comunidade cobre (limitação aceita).
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from domain.enums import SpoilerCheckStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from repositories.review import ReviewRepository
    from services.spoiler import SpoilerCheckService

logger = logging.getLogger("uvicorn.error")

MAX_WORKERS = 2


class SpoilerScheduler(Protocol):
    """O que o `ReviewService` precisa: agendar sem esperar nem falhar."""

    def schedule(self, review_id: UUID) -> None: ...


class SpoilerReviewJob:
    """Uma análise: lê a avaliação, consulta a IA e liga a flag se for SIM."""

    def __init__(
        self,
        session_factory: Callable[[], "Session"],
        repository_factory: Callable[["Session"], "ReviewRepository"],
        checker_factory: Callable[[], "SpoilerCheckService"],
    ) -> None:
        self.session_factory = session_factory
        self.repository_factory = repository_factory
        self.checker_factory = checker_factory

    def __call__(self, review_id: UUID) -> None:
        session = self.session_factory()
        try:
            repository = self.repository_factory(session)
            review = repository.get(review_id)
            if review is None:
                logger.info("Análise de spoiler: avaliação=%s ausente.", review_id)
                return
            if review.is_spoiler:
                logger.info(
                    "Análise de spoiler: avaliação=%s já marcada, IA não chamada.",
                    review_id,
                )
                return
            movie_id, content = review.movie_id, review.content
            # Encerra a leitura antes da IA: nada de transação aberta esperando.
            session.rollback()

            analysis = self.checker_factory().analyze(movie_id, content)
            marked = (
                analysis.status == SpoilerCheckStatus.SUSPECTED
                and repository.mark_spoiler(review_id)
            )
            logger.info(
                "Análise de spoiler: avaliação=%s resultado=%s sinopse=%s marcada=%s.",
                review_id,
                analysis.status.value,
                "sim" if analysis.had_synopsis else "não",
                "sim" if marked else "não",
            )
        finally:
            session.close()


class SpoilerReviewScheduler:
    """Pool pequeno de threads do processo, injetado no `ReviewService`."""

    def __init__(
        self, job: Callable[[UUID], None], *, max_workers: int = MAX_WORKERS
    ) -> None:
        self.job = job
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="spoiler-review"
        )

    def schedule(self, review_id: UUID) -> None:
        try:
            self._executor.submit(self._run, review_id)
        except RuntimeError:
            # Pool encerrado (desligando o processo): a publicação segue.
            logger.warning(
                "Análise de spoiler não agendada: avaliação=%s (pool encerrado).",
                review_id,
            )

    def _run(self, review_id: UUID) -> None:
        try:
            self.job(review_id)
        except Exception:
            logger.exception("Falha na análise de spoiler: avaliação=%s.", review_id)

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
