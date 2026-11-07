"""Base ORM e engine PostgreSQL compartilhados com o Alembic."""

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config  # noqa: F401 — carrega .env sem sobrescrever o ambiente


class Base(DeclarativeBase):
    pass


class DatabaseConfigurationError(RuntimeError):
    pass


def get_database_url() -> URL:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise DatabaseConfigurationError("DATABASE_URL não configurada.")
    try:
        url = make_url(value)
    except (ArgumentError, ValueError) as exc:
        raise DatabaseConfigurationError("DATABASE_URL inválida.") from exc
    if url.drivername != "postgresql+psycopg":
        raise DatabaseConfigurationError("Utilize PostgreSQL com psycopg 3.")
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
    )


def create_session() -> Session:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return factory()
