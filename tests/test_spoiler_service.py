"""Cenários 4 e 5 da SPEC-BACK-09 no serviço: só sugere, nunca bloqueia."""

from unittest.mock import Mock

import pytest

from domain.enums import SpoilerCheckStatus
from services.ai import AIUnavailableError
from services.spoiler import SpoilerCheckService

MOVIE_ID = "tt0133093"
DRAFT = "No final, o Neo descobre que tudo era uma simulação."


@pytest.fixture
def chat():
    client = Mock()
    client.configured = True
    return client


@pytest.fixture
def titles():
    return Mock(return_value="Matrix (1999)")


def service(chat, titles):
    return SpoilerCheckService(chat, titles, timeout=4)


@pytest.mark.parametrize(
    ("answer", "status"),
    [("SIM", SpoilerCheckStatus.SUSPECTED), ("NAO", SpoilerCheckStatus.CLEAR)],
)
def test_returns_ai_classification(chat, titles, answer, status):
    chat.complete.return_value = answer

    assert service(chat, titles).check(MOVIE_ID, DRAFT) == status
    messages = chat.complete.call_args.args[0]
    assert DRAFT in messages[1]["content"]
    assert "Matrix (1999)" in messages[1]["content"]
    assert chat.complete.call_args.kwargs["timeout"] == 4
    titles.assert_called_once_with(MOVIE_ID)


def test_scenario_5_ai_failure_is_unavailable(chat, titles):
    chat.complete.side_effect = AIUnavailableError("timeout")
    assert service(chat, titles).check(MOVIE_ID, DRAFT) == (
        SpoilerCheckStatus.UNAVAILABLE
    )


def test_unexpected_answer_is_unavailable(chat, titles):
    chat.complete.return_value = "Depende do ponto de vista."
    assert service(chat, titles).check(MOVIE_ID, DRAFT) == (
        SpoilerCheckStatus.UNAVAILABLE
    )


def test_unconfigured_ai_skips_title_lookup(chat, titles):
    chat.configured = False
    assert service(chat, titles).check(MOVIE_ID, DRAFT) == (
        SpoilerCheckStatus.UNAVAILABLE
    )
    titles.assert_not_called()
    chat.complete.assert_not_called()
