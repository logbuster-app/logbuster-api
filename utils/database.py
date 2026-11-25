"""Base ORM e engine SQLite compartilhados com o Alembic."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config  # noqa: F401 — carrega .env sem sobrescrever o ambiente


class Base(DeclarativeBase):
    pass


class DatabaseConfigurationError(RuntimeError):
    pass


@event.listens_for(Engine, "connect")
def _configure_sqlite_connection(dbapi_connection: Any, _connection_record: Any) -> None:
    if not dbapi_connection.__class__.__module__.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def get_database_url() -> URL:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise DatabaseConfigurationError("DATABASE_URL não configurada.")
    try:
        url = make_url(value)
    except (ArgumentError, ValueError) as exc:
        raise DatabaseConfigurationError("DATABASE_URL inválida.") from exc
    if url.drivername not in {"sqlite", "sqlite+pysqlite"}:
        raise DatabaseConfigurationError("Utilize SQLite (sqlite:///...).")
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"check_same_thread": False, "timeout": 30},
    )


def create_session() -> Session:
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return factory()
