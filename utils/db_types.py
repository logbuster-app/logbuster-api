"""Tipos portáveis do SQLAlchemy para SQLite (listas JSON e datetimes UTC)."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Garante datetimes com `tzinfo=UTC` ao ler colunas `DATETIME` do SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True
    timezone = True

    def process_bind_param(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(UTC)
        return value

    def process_result_value(
        self, value: datetime | None, dialect: Dialect
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class StringList(TypeDecorator[list[str]]):
    """Armazena `list[str]` como array JSON em coluna TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: list[str] | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        return json.dumps(list(value))

    def process_result_value(
        self, value: str | list[str] | None, dialect: Dialect
    ) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(item) for item in json.loads(value)]


class UuidList(TypeDecorator[list[UUID]]):
    """Armazena `list[UUID]` como array JSON de strings em coluna TEXT."""

    impl = Text
    cache_ok = True

    def process_bind_param(
        self, value: list[UUID] | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return None
        return json.dumps([str(item) for item in value])

    def process_result_value(
        self, value: str | list[str | UUID] | None, dialect: Dialect
    ) -> list[UUID]:
        if value is None:
            return []
        raw = value if isinstance(value, list) else json.loads(value)
        return [item if isinstance(item, UUID) else UUID(str(item)) for item in raw]
