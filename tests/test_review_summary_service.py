"""Cenários 1 a 3 da SPEC-BACK-09: limiar, filtro de spoiler, cache e falhas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from domain.enums import ReviewSummaryStatus, SpoilerCheckStatus
from services.ai import AIUnavailableError
from services.review_summary import MIN_REVIEWS, ReviewSummaryService

MOVIE_ID = "tt0133093"
NOW = datetime(2026, 11, 23, 15, 0, tzinfo=UTC)
SUMMARY = (
    "A comunidade elogia a direção e a trilha sonora, mas critica o ritmo do "
    "segundo ato."
)


def row(content, *, rating="4.0", highlights=("direction",)):
    review = SimpleNamespace(
        id=uuid4(),
        rating=Decimal(rating),
        highlights=list(highlights),
        content=content,
    )
    return SimpleNamespace(review=review, like=0, spoiler=0, well_argued=0)


def cached(*, text=SUMMARY, reviews_count=3, sources=(), failed_at=None):
    return SimpleNamespace(
        text=text,
        generated_at=NOW - timedelta(hours=1) if text else None,
        reviews_count=reviews_count,
        source_review_ids=list(sources),
        failed_at=failed_at,
    )


@pytest.fixture
def reviews():
    repository = Mock()
    repository.count.return_value = 3
    repository.eligible_ids.side_effect = lambda ids: set(ids)
    return repository


@pytest.fixture
def summaries():
    repository = Mock()
    repository.get.return_value = None
    repository.try_lock.return_value = True
    return repository


@pytest.fixture
def chat():
    client = Mock()
    client.configured = True
    client.complete.return_value = SUMMARY
    return client


@pytest.fixture
def spoiler_checker():
    return Mock(return_value=SpoilerCheckStatus.CLEAR)


@pytest.fixture
def service(reviews, summaries, chat, spoiler_checker):
    return ReviewSummaryService(
        reviews,
        summaries,
        chat,
        title_lookup=lambda movie_id: "Matrix (1999)",
        spoiler_checker=spoiler_checker,
        regen_threshold=3,
        retry_after_seconds=60,
        timeout=5,
        now=lambda: NOW,
    )


@pytest.mark.parametrize("count", [0, 1, 2])
def test_scenario_1_below_minimum_never_calls_ai(
    service, reviews, summaries, chat, count
):
    reviews.count.return_value = count

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.INSUFFICIENT_REVIEWS
    assert result.text is None and result.generated_at is None
    assert MIN_REVIEWS == 3
    chat.complete.assert_not_called()
    summaries.get.assert_not_called()


def test_scenario_2_generates_with_eligible_texts_only(
    service, reviews, summaries, chat
):
    eligible = [row("Direção precisa e trilha marcante."), row("Ritmo lento demais.")]
    reviews.summary_candidates.return_value = eligible

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.READY
    assert result.text == SUMMARY
    assert result.generated_at == NOW
    # O repositório já exclui spoilers do autor e com 3 votos (teste de SQL).
    reviews.summary_candidates.assert_called_once()
    prompt = chat.complete.call_args.args[0][1]["content"]
    assert "Direção precisa e trilha marcante." in prompt
    assert "Ritmo lento demais." in prompt
    assert "Matrix (1999)" in prompt
    summaries.save_success.assert_called_once_with(
        MOVIE_ID,
        text=SUMMARY,
        generated_at=NOW,
        reviews_count=3,
        source_review_ids=[item.review.id for item in eligible],
    )


def test_scenario_2_reuses_cache_until_threshold(service, reviews, summaries, chat):
    source = uuid4()
    summaries.get.return_value = cached(reviews_count=3, sources=[source])

    for total in (3, 4, 5):
        reviews.count.return_value = total
        result = service.get(MOVIE_ID)
        assert result.status == ReviewSummaryStatus.READY
        assert result.text == SUMMARY

    chat.complete.assert_not_called()
    summaries.try_lock.assert_not_called()


def test_scenario_2_regenerates_when_threshold_is_reached(
    service, reviews, summaries, chat
):
    summaries.get.return_value = cached(reviews_count=3, sources=[uuid4()])
    reviews.count.return_value = 6
    reviews.summary_candidates.return_value = [row("Uma avaliação nova e elegível.")]
    chat.complete.return_value = SUMMARY + " Novas avaliações reforçam isso."

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.READY
    assert result.text.endswith("Novas avaliações reforçam isso.")
    assert summaries.save_success.call_args.kwargs["reviews_count"] == 6


def test_scenario_3_cache_using_newly_hidden_review_is_not_served(
    service, reviews, summaries, chat
):
    hidden, kept = uuid4(), uuid4()
    summaries.get.return_value = cached(sources=[hidden, kept])
    reviews.eligible_ids.side_effect = lambda ids: {kept}
    reviews.summary_candidates.return_value = [row("Texto que continua elegível.")]
    chat.complete.side_effect = AIUnavailableError("timeout")

    result = service.get(MOVIE_ID)

    # Sem nova geração elegível: indisponível, sem revelar o texto antigo.
    assert result.status == ReviewSummaryStatus.UNAVAILABLE
    assert result.text is None
    summaries.save_failure.assert_called_once_with(MOVIE_ID, failed_at=NOW)


def test_scenario_3_hidden_review_triggers_new_eligible_generation(
    service, reviews, summaries
):
    hidden = uuid4()
    summaries.get.return_value = cached(sources=[hidden])
    reviews.eligible_ids.side_effect = lambda ids: set()
    reviews.summary_candidates.return_value = [row("Outra avaliação sem spoiler.")]

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.READY
    sources = summaries.save_success.call_args.kwargs["source_review_ids"]
    assert hidden not in sources


def test_scenario_3_ai_failure_records_and_backs_off(service, summaries, chat, reviews):
    reviews.summary_candidates.return_value = [row("Avaliação elegível qualquer.")]
    chat.complete.side_effect = AIUnavailableError("erro")

    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    summaries.save_failure.assert_called_once_with(MOVIE_ID, failed_at=NOW)

    # Dentro da espera, nem trava nem IA são acionadas de novo.
    summaries.get.return_value = cached(
        text=None, failed_at=NOW - timedelta(seconds=30)
    )
    chat.complete.reset_mock()
    summaries.try_lock.reset_mock()
    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    chat.complete.assert_not_called()
    summaries.try_lock.assert_not_called()

    # Depois da espera, tenta de novo.
    summaries.get.return_value = cached(text=None, failed_at=NOW - timedelta(minutes=2))
    chat.complete.side_effect = None
    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.READY


def test_scenario_3_without_eligible_text_is_unavailable(
    service, reviews, summaries, chat
):
    reviews.summary_candidates.return_value = []

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.UNAVAILABLE
    chat.complete.assert_not_called()
    summaries.release.assert_called_once()
    summaries.save_failure.assert_not_called()


@pytest.mark.parametrize("answer", ["Curto.", "x" * 2000])
def test_improper_answer_is_unavailable(service, reviews, summaries, chat, answer):
    reviews.summary_candidates.return_value = [row("Avaliação elegível qualquer.")]
    chat.complete.return_value = answer

    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    summaries.save_success.assert_not_called()
    summaries.save_failure.assert_called_once()


def test_summary_flagged_as_spoiler_is_discarded(
    service, reviews, summaries, spoiler_checker
):
    reviews.summary_candidates.return_value = [row("Avaliação elegível qualquer.")]
    spoiler_checker.return_value = SpoilerCheckStatus.SUSPECTED

    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    spoiler_checker.assert_called_once_with(MOVIE_ID, SUMMARY)
    summaries.save_success.assert_not_called()


def test_unavailable_spoiler_guard_does_not_block_summary(
    service, reviews, spoiler_checker
):
    reviews.summary_candidates.return_value = [row("Avaliação elegível qualquer.")]
    spoiler_checker.return_value = SpoilerCheckStatus.UNAVAILABLE

    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.READY


def test_one_generation_per_movie(service, summaries, chat):
    summaries.try_lock.return_value = False

    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    chat.complete.assert_not_called()


def test_rechecks_cache_after_acquiring_lock(service, summaries, chat):
    fresh = cached(sources=[])
    summaries.get.side_effect = [None, fresh]

    result = service.get(MOVIE_ID)

    assert result.status == ReviewSummaryStatus.READY
    summaries.get.assert_called_with(MOVIE_ID, refresh=True)
    summaries.release.assert_called_once()
    chat.complete.assert_not_called()


def test_unconfigured_ai_is_unavailable_but_valid_cache_is_still_served(
    service, summaries, chat
):
    chat.configured = False
    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.UNAVAILABLE
    summaries.try_lock.assert_not_called()

    summaries.get.return_value = cached(sources=[])
    assert service.get(MOVIE_ID).status == ReviewSummaryStatus.READY
