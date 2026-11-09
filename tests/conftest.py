import os
import socket
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dependencies.services import get_interaction_service, get_review_service
from domain.models.review import Review
from repositories.review import ReviewRepository
from services.interaction import InteractionService
from services.review import ReviewService
from utils.database import get_engine

with patch.dict(
    os.environ,
    {"APP_ENV": "test", "CORS_ALLOWED_ORIGINS": "http://localhost:3000"},
):
    from main import app

MOVIE_ID = "tt0133093"


@pytest.fixture(autouse=True)
def isolate_infrastructure():
    """Toda a suíte falha se tentar abrir banco ou conexão de rede real."""
    get_engine.cache_clear()
    with (
        patch("utils.database.create_engine", side_effect=AssertionError("Banco real")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("Rede real")
        ),
        patch.object(socket.socket, "connect", side_effect=AssertionError("Rede real")),
    ):
        yield
    get_engine.cache_clear()


@pytest.fixture
def session():
    return MagicMock(spec=Session)


@pytest.fixture
def review_payload():
    return {
        "movie_id": MOVIE_ID,
        "author_name": "Thyago",
        "rating": 4.5,
        "content": "Direção precisa e efeitos visuais que revolucionaram o gênero.",
        "is_spoiler": False,
        "highlights": ["direction", "visual_effects"],
    }


@pytest.fixture
def review():
    return Review(
        id=uuid4(),
        movie_id=MOVIE_ID,
        author_name="Thyago",
        rating=Decimal("4.5"),
        content="Direção precisa e efeitos visuais que revolucionaram o gênero.",
        is_spoiler=False,
        highlights=["direction", "visual_effects"],
        created_at=datetime(2026, 11, 8, 18, 30, tzinfo=UTC),
    )


@pytest.fixture
def review_repository():
    return Mock(spec=ReviewRepository)


@pytest.fixture
def review_service():
    return Mock(spec=ReviewService)


@pytest.fixture
def interaction_service():
    return Mock(spec=InteractionService)


@pytest.fixture
def client(review_service, interaction_service):
    app.dependency_overrides[get_review_service] = lambda: review_service
    app.dependency_overrides[get_interaction_service] = lambda: interaction_service
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
