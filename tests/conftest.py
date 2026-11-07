import os
import socket
from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from dependencies.services import get_interaction_service, get_review_service
from domain.enums import InteractionType
from domain.models.interaction import Interaction
from domain.models.review import Review
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository
from services.interaction import InteractionService
from services.review import ReviewService
from utils.database import get_engine

with patch.dict(
    os.environ,
    {"APP_ENV": "test", "CORS_ALLOWED_ORIGINS": "http://localhost:3000"},
):
    from main import app


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
def review():
    return Review(
        id=uuid4(),
        movie_id="catalog:42",
        user_id="user-1",
        rating=5,
        comment="Excelente filme!",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def interaction():
    return Interaction(
        id=uuid4(),
        movie_id="catalog:42",
        user_id="user-1",
        interaction_type=InteractionType.LIKE,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def review_repository():
    return Mock(spec=ReviewRepository)


@pytest.fixture
def interaction_repository():
    return Mock(spec=InteractionRepository)


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
