"""Análise de spoiler pela IA: contexto do filme e falhas (CR-02)."""

from unittest.mock import Mock

import pytest

from domain.enums import SpoilerCheckStatus
from services.ai import AIUnavailableError
from services.movie_titles import MovieContext
from services.spoiler import SpoilerAnalysis, SpoilerCheckService

MOVIE_ID = "tt0133093"
DRAFT = "No final, o Neo descobre que tudo era uma simulação."
MATRIX = MovieContext(
    "Matrix", "1999", "Um hacker descobre a verdade sobre a realidade."
)


@pytest.fixture
def chat():
    client = Mock()
    client.configured = True
    return client


@pytest.fixture
def contexts():
    return Mock(return_value=MATRIX)


def service(chat, contexts):
    return SpoilerCheckService(chat, contexts, timeout=4)


@pytest.mark.parametrize(
    ("answer", "status"),
    [("SIM", SpoilerCheckStatus.SUSPECTED), ("NAO", SpoilerCheckStatus.CLEAR)],
)
def test_sends_title_year_synopsis_and_full_text(chat, contexts, answer, status):
    chat.complete.return_value = answer

    result = service(chat, contexts).analyze(MOVIE_ID, DRAFT)

    assert result == SpoilerAnalysis(status, had_synopsis=True)
    prompt = chat.complete.call_args.args[0][1]["content"]
    assert prompt.startswith("Filme: Matrix (1999) (tt0133093)")
    assert "<sinopse>\nUm hacker descobre a verdade sobre a realidade.\n</sinopse>" in (
        prompt
    )
    assert f"<avaliacao>\n{DRAFT}\n</avaliacao>" in prompt
    assert chat.complete.call_args.kwargs["timeout"] == 4
    contexts.assert_called_once_with(MOVIE_ID)


def test_check_returns_only_status(chat, contexts):
    chat.complete.return_value = "SIM"
    assert service(chat, contexts).check(MOVIE_ID, DRAFT) == (
        SpoilerCheckStatus.SUSPECTED
    )


def test_without_synopsis_runs_with_title_only(chat, contexts):
    contexts.return_value = MovieContext("Matrix", "1999")
    chat.complete.return_value = "NAO"

    result = service(chat, contexts).analyze(MOVIE_ID, DRAFT)

    assert result == SpoilerAnalysis(SpoilerCheckStatus.CLEAR, had_synopsis=False)
    assert "<sinopse>" not in chat.complete.call_args.args[0][1]["content"]


def test_omdb_down_runs_with_movie_id_only(chat, contexts):
    contexts.return_value = None
    chat.complete.return_value = "SIM"

    result = service(chat, contexts).analyze(MOVIE_ID, DRAFT)

    assert result == SpoilerAnalysis(SpoilerCheckStatus.SUSPECTED, had_synopsis=False)
    assert chat.complete.call_args.args[0][1]["content"].startswith(
        "Filme: tt0133093\n"
    )


def test_ai_failure_is_unavailable(chat, contexts):
    chat.complete.side_effect = AIUnavailableError("timeout")
    result = service(chat, contexts).analyze(MOVIE_ID, DRAFT)
    assert result == SpoilerAnalysis(SpoilerCheckStatus.UNAVAILABLE, had_synopsis=True)


def test_unexpected_answer_is_unavailable(chat, contexts):
    chat.complete.return_value = "Depende do ponto de vista."
    assert service(chat, contexts).check(MOVIE_ID, DRAFT) == (
        SpoilerCheckStatus.UNAVAILABLE
    )


def test_unconfigured_ai_skips_omdb(chat, contexts):
    chat.configured = False
    result = service(chat, contexts).analyze(MOVIE_ID, DRAFT)
    assert result == SpoilerAnalysis(SpoilerCheckStatus.UNAVAILABLE, had_synopsis=False)
    contexts.assert_not_called()
    chat.complete.assert_not_called()
