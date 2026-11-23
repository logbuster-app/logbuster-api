"""CR-02: análise de spoiler depois de publicar, com sessão, IA e OMDb falsas."""

import logging
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from domain.enums import SpoilerCheckStatus
from services.spoiler import SpoilerAnalysis
from services.spoiler_scheduler import (
    MAX_WORKERS,
    SpoilerReviewJob,
    SpoilerReviewScheduler,
)

REVIEW_ID = uuid4()
SECRET_TEXT = "No final o Neo morre e revive, texto-secreto-do-autor."


def stored_review(*, is_spoiler=False):
    return SimpleNamespace(
        id=REVIEW_ID, movie_id="tt0133093", content=SECRET_TEXT, is_spoiler=is_spoiler
    )


@pytest.fixture
def session():
    return Mock()


@pytest.fixture
def repository():
    repo = Mock()
    repo.get.return_value = stored_review()
    repo.mark_spoiler.return_value = True
    return repo


@pytest.fixture
def checker():
    service = Mock()
    service.analyze.return_value = SpoilerAnalysis(
        SpoilerCheckStatus.SUSPECTED, had_synopsis=True
    )
    return service


@pytest.fixture
def job(session, repository, checker):
    return SpoilerReviewJob(
        session_factory=lambda: session,
        repository_factory=lambda _session: repository,
        checker_factory=lambda: checker,
    )


def test_scenario_2_suspected_turns_flag_on(job, repository, checker, session):
    job(REVIEW_ID)

    checker.analyze.assert_called_once_with("tt0133093", SECRET_TEXT)
    repository.mark_spoiler.assert_called_once_with(REVIEW_ID)
    session.close.assert_called_once()


@pytest.mark.parametrize(
    "status", [SpoilerCheckStatus.CLEAR, SpoilerCheckStatus.UNAVAILABLE]
)
def test_scenarios_3_and_6_clear_or_failure_change_nothing(
    job, repository, checker, status
):
    checker.analyze.return_value = SpoilerAnalysis(status, had_synopsis=False)

    job(REVIEW_ID)

    repository.mark_spoiler.assert_not_called()


def test_scenario_4_already_marked_does_not_call_ai(job, repository, checker, session):
    repository.get.return_value = stored_review(is_spoiler=True)

    job(REVIEW_ID)

    checker.analyze.assert_not_called()
    repository.mark_spoiler.assert_not_called()
    session.close.assert_called_once()


def test_missing_review_is_skipped(job, repository, checker):
    repository.get.return_value = None
    job(REVIEW_ID)
    checker.analyze.assert_not_called()


def test_read_transaction_ends_before_calling_ai(job, session, checker):
    calls = []
    session.rollback.side_effect = lambda: calls.append("rollback")
    checker.analyze.side_effect = lambda *_: (
        calls.append("ia")
        or SpoilerAnalysis(SpoilerCheckStatus.CLEAR, had_synopsis=True)
    )

    job(REVIEW_ID)

    assert calls == ["rollback", "ia"]


def test_session_closes_even_when_ai_raises(job, session, checker):
    checker.analyze.side_effect = RuntimeError("falha inesperada")
    with pytest.raises(RuntimeError):
        job(REVIEW_ID)
    session.close.assert_called_once()


def test_log_has_id_result_and_synopsis_but_never_the_text(job, caplog):
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        job(REVIEW_ID)

    assert str(REVIEW_ID) in caplog.text
    assert "resultado=suspected" in caplog.text
    assert "sinopse=sim" in caplog.text
    assert "marcada=sim" in caplog.text
    assert "texto-secreto-do-autor" not in caplog.text


def test_scheduler_runs_job_outside_the_caller_thread():
    seen = []
    done = threading.Event()

    def job(review_id):
        seen.append((review_id, threading.current_thread().name))
        done.set()

    scheduler = SpoilerReviewScheduler(job)
    scheduler.schedule(REVIEW_ID)
    assert done.wait(timeout=5)
    scheduler.shutdown(wait=True)

    assert seen[0][0] == REVIEW_ID
    assert seen[0][1].startswith("spoiler-review")
    assert scheduler._executor._max_workers == MAX_WORKERS == 2


def test_scheduler_logs_job_errors_without_raising(caplog):
    done = threading.Event()

    def failing_job(_review_id):
        done.set()
        raise RuntimeError("IA fora do ar")

    scheduler = SpoilerReviewScheduler(failing_job)
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        scheduler.schedule(REVIEW_ID)
        assert done.wait(timeout=5)
        scheduler.shutdown(wait=True)

    assert "Falha na análise de spoiler" in caplog.text


def test_schedule_after_shutdown_does_not_raise(caplog):
    scheduler = SpoilerReviewScheduler(Mock())
    scheduler.shutdown()

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        scheduler.schedule(REVIEW_ID)

    assert "não agendada" in caplog.text
