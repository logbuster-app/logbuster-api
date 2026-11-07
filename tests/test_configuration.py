from unittest.mock import patch

import pytest

from config import Settings
from dependencies.services import get_interaction_service, get_review_service
from dependencies.session import get_session
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository
from utils.database import (
    DatabaseConfigurationError,
    create_session,
    get_database_url,
    get_engine,
)


def test_database_url_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(DatabaseConfigurationError):
        get_database_url()


@pytest.mark.parametrize(
    "url", ["invalid", "sqlite://", "postgresql://user@localhost/db"]
)
def test_database_requires_postgresql_psycopg3(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", url)
    with pytest.raises(DatabaseConfigurationError):
        get_database_url()


def test_engine_is_lazy_cached_and_hides_parameters(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user@localhost/db")
    with patch("utils.database.create_engine") as factory:
        assert get_engine() is get_engine()
        factory.assert_called_once()
        assert factory.call_args.kwargs["hide_parameters"] is True
        assert factory.call_args.kwargs["connect_args"]["options"] == "-c timezone=UTC"


def test_session_factory_does_not_expire_committed_entities():
    with (
        patch("utils.database.get_engine"),
        patch("utils.database.sessionmaker") as maker,
    ):
        assert create_session() is maker.return_value.return_value
        assert maker.call_args.kwargs["expire_on_commit"] is False
        assert maker.call_args.kwargs["autoflush"] is False


def test_session_closes_after_success(session):
    with patch("dependencies.session.create_session", return_value=session):
        dependency = get_session()
        assert next(dependency) is session
        with pytest.raises(StopIteration):
            next(dependency)
    session.close.assert_called_once()
    session.commit.assert_not_called()


def test_session_rolls_back_and_closes_after_failure(session):
    with patch("dependencies.session.create_session", return_value=session):
        dependency = get_session()
        next(dependency)
        with pytest.raises(RuntimeError):
            dependency.throw(RuntimeError("Erro de consulta"))
    session.rollback.assert_called_once()
    session.close.assert_called_once()


def test_dependency_factories_wire_repositories(session):
    review_service = get_review_service(session)
    interaction_service = get_interaction_service(session)
    assert isinstance(review_service.repository, ReviewRepository)
    assert isinstance(interaction_service.repository, InteractionRepository)
    assert review_service.repository.session is session
    assert interaction_service.repository.session is session


def test_cors_parses_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", " https://example.com, http://localhost:3000, "
    )
    assert Settings().cors_allowed_origins == [
        "https://example.com",
        "http://localhost:3000",
    ]


def test_production_defaults_to_no_cors_origins(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert Settings().cors_allowed_origins == []
