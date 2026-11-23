"""Contrato HTTP da SPEC-BACK-09 com o CR-02: resumo, rota removida e arquétipo."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from dependencies.services import (
    build_spoiler_check_service,
    get_chat_client,
    get_review_summary_service,
    get_title_lookup,
)
from dependencies.session import get_session
from domain.models.review import Review
from domain.models.user import User
from domain.schemas.ai import ReviewSummaryResponse
from domain.schemas.reviews import ReviewResponse
from main import app
from repositories.review import ReviewRepository
from repositories.review_summary import ReviewSummaryRepository
from services.ai import ChatClient
from services.review_summary import ReviewSummaryService

MOVIE_ID = "tt0133093"
SUMMARY_ROUTE = f"/api/v1/movies/{MOVIE_ID}/review-summary"
SPOILER_ROUTE = "/api/v1/reviews/spoiler-check"
DRAFT = "No final, o Neo descobre que tudo era uma simulação."


@pytest.fixture
def ai_client(client):
    summary = Mock(spec=ReviewSummaryService)
    app.dependency_overrides[get_review_summary_service] = lambda: summary
    return client, summary


def test_summary_ready_contract(ai_client):
    client, summary = ai_client
    summary.get.return_value = ReviewSummaryResponse.ready(
        "A comunidade destaca a direção e a trilha sonora do filme.",
        datetime(2026, 11, 23, 15, tzinfo=UTC),
    )

    response = client.get(SUMMARY_ROUTE)

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "text": "A comunidade destaca a direção e a trilha sonora do filme.",
        "generated_at": "2026-11-23T15:00:00Z",
    }
    summary.get.assert_called_once_with(MOVIE_ID)


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (ReviewSummaryResponse.insufficient(), "insufficient_reviews"),
        (ReviewSummaryResponse.unavailable(), "unavailable"),
    ],
)
def test_summary_without_text_keeps_nulls(ai_client, result, status):
    client, summary = ai_client
    summary.get.return_value = result

    response = client.get(SUMMARY_ROUTE)

    assert response.status_code == 200
    assert response.json() == {"status": status, "text": None, "generated_at": None}


def test_summary_rejects_malformed_movie_id(ai_client):
    client, summary = ai_client

    response = client.get("/api/v1/movies/matrix/review-summary")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    summary.get.assert_not_called()


# --- CR-02: rota de checagem de rascunho removida ---------------------------


@pytest.mark.parametrize("body", [{"movie_id": MOVIE_ID, "content": DRAFT}, {}, None])
def test_cr02_scenario_8_removed_spoiler_check_returns_404(
    client, review_service, body
):
    response = client.post(SPOILER_ROUTE, json=body)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert review_service.mock_calls == []


def test_cr02_removed_route_is_not_documented(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    assert SPOILER_ROUTE not in paths
    assert "IA" in paths["/api/v1/movies/{movie_id}/review-summary"]["get"]["tags"]
    assert "SpoilerCheckRequest" not in str(paths)


def test_cr02_publication_contract_is_unchanged(
    authenticated_client, review_service, review_payload, review
):
    review_service.create_for_user.return_value = ReviewResponse.from_model(review)

    response = authenticated_client.post(
        "/api/v1/reviews", json={**review_payload, "is_spoiler": False}
    )

    assert response.status_code == 201
    assert response.json()["is_spoiler"] is False
    assert review_service.create_for_user.call_args.args[0].is_spoiler is False


def test_dependencies_build_services_from_settings(monkeypatch, session):
    monkeypatch.setenv("AI_BASE_URL", "https://ia.test/v1/")
    monkeypatch.setenv("AI_API_KEY", "chave")
    monkeypatch.setenv("AI_MODEL", "modelo")
    monkeypatch.setenv("AI_REASONING_EFFORT", " low ")
    monkeypatch.setenv("AI_SPOILER_TIMEOUT_SECONDS", "4")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("REVIEW_SUMMARY_REGEN_THRESHOLD", "5")

    chat = get_chat_client()
    assert isinstance(chat, ChatClient) and chat.configured
    assert chat.base_url == "https://ia.test/v1"
    assert chat.reasoning_effort == "low"
    titles = get_title_lookup()

    spoiler = build_spoiler_check_service()
    assert spoiler.timeout == 4
    assert spoiler.chat.configured

    summary = get_review_summary_service(session, chat, titles)
    assert isinstance(summary.reviews, ReviewRepository)
    assert isinstance(summary.summaries, ReviewSummaryRepository)
    assert summary.regen_threshold == 5
    assert summary.timeout == 12


def test_ai_is_unavailable_by_default(monkeypatch):
    for name in ("AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert get_chat_client().configured is False


# --- Cenário 6: arquétipo no perfil público -------------------------------


@pytest.fixture
def profile_client(session):
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def account():
    return User(
        id=uuid4(),
        display_name="Pessoa cinéfila",
        email="cinefila@example.com",
        password_hash="hash",
        bio=None,
        avatar_id=None,
        created_at=datetime(2026, 11, 20, 14, tzinfo=UTC),
    )


def owned_review(user, rating):
    return Review(
        id=uuid4(),
        movie_id=MOVIE_ID,
        author_name=user.display_name,
        user_id=user.id,
        rating=Decimal(rating),
        content="Uma avaliação vinculada à conta.",
        is_spoiler=False,
        highlights=["direction"],
        created_at=datetime(2026, 11, 21, tzinfo=UTC),
    )


def test_scenario_6_archetype_appears_from_third_review(profile_client, session):
    user = account()
    session.get.return_value = user
    rows = [(owned_review(user, "5.0"), 0, 0, 0), (owned_review(user, "4.5"), 0, 0, 0)]
    session.execute.return_value = rows

    first = profile_client.get(f"/api/v1/users/{user.id}")
    assert first.status_code == 200
    assert first.json()["archetype"] is None

    rows.append((owned_review(user, "5.0"), 0, 0, 0))
    second = profile_client.get(f"/api/v1/users/{user.id}")
    assert second.json()["archetype"] == {
        "title": "Coração mole",
        "description": "Média de 4,8 estrelas: encontra algo para amar em quase "
        "todo filme.",
    }
    query = str(session.execute.call_args.args[0])
    assert "reviews.user_id" in query


def test_archetype_uses_votes_received_and_follows_data_changes(
    profile_client, session
):
    user = account()
    session.get.return_value = user
    session.execute.return_value = [
        (owned_review(user, "3.0"), 0, 0, 3) for _ in range(3)
    ]
    assert (
        profile_client.get(f"/api/v1/users/{user.id}").json()["archetype"]["title"]
        == "Voz da comunidade"
    )

    session.execute.return_value = [
        (owned_review(user, "1.0"), 0, 0, 0) for _ in range(3)
    ]
    assert (
        profile_client.get(f"/api/v1/users/{user.id}").json()["archetype"]["title"]
        == "Crítico exigente"
    )


# --- CR-02: agendador real só existe uma vez por processo -----------------


def test_spoiler_scheduler_is_a_process_singleton_and_shuts_down():
    from dependencies.services import (
        get_spoiler_scheduler,
        shutdown_spoiler_scheduler,
    )
    from services.spoiler_scheduler import SpoilerReviewJob, SpoilerReviewScheduler

    shutdown_spoiler_scheduler()
    first = get_spoiler_scheduler()
    assert isinstance(first, SpoilerReviewScheduler)
    assert isinstance(first.job, SpoilerReviewJob)
    assert get_spoiler_scheduler() is first

    shutdown_spoiler_scheduler()
    assert get_spoiler_scheduler.cache_info().currsize == 0
    shutdown_spoiler_scheduler()  # sem pool criado, não faz nada


def test_real_review_service_dependency_receives_scheduler(session, spoiler_scheduler):
    from dependencies.services import get_review_service

    service = get_review_service(session, spoiler_scheduler)
    assert service.spoiler_scheduler is spoiler_scheduler
