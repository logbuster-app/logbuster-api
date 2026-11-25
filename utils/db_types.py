"""Tipos portáveis do SQLAlchemy para armazenamento de listas em SQLite."""

import json
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


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
