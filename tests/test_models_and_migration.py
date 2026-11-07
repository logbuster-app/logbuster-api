import importlib.util
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index, MetaData, Table, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from domain.models import Interaction, Review
from domain.schemas.movies import ReviewRead
from utils.database import Base


def load_initial_migration():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/0001_create_reviews_and_interactions.py"
    )
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def table_signature(table):
    dialect = postgresql.dialect()
    return {
        "columns": [
            (
                col.name,
                str(col.type.compile(dialect=dialect)),
                col.nullable,
                str(col.server_default.arg) if col.server_default else None,
            )
            for col in table.columns
        ],
        "primary_key": tuple(col.name for col in table.primary_key),
        "unique": {
            (constraint.name, tuple(col.name for col in constraint.columns))
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        },
        "checks": {
            (
                str(constraint.name),
                str(
                    constraint.sqltext.compile(
                        dialect=dialect, compile_kwargs={"literal_binds": True}
                    )
                ),
            )
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint)
        },
        "indexes": {
            (idx.name, tuple(col.name for col in idx.columns)) for idx in table.indexes
        },
    }


def test_migration_matches_models_without_database():
    metadata = MetaData()
    operations = MagicMock()
    operations.create_table.side_effect = lambda name, *args: Table(
        name, metadata, *args
    )

    def create_index(name, table_name, columns):
        table = metadata.tables[table_name]
        Index(name, *(table.c[col] for col in columns))

    operations.create_index.side_effect = create_index
    migration = load_initial_migration()
    with patch.object(migration, "op", operations):
        migration.upgrade()
    assert (
        set(metadata.tables) == set(Base.metadata.tables) == {"reviews", "interactions"}
    )
    for name, table in metadata.tables.items():
        assert table_signature(table) == table_signature(Base.metadata.tables[name])


def test_migration_downgrade_removes_indexes_and_tables():
    migration = load_initial_migration()
    with patch.object(migration, "op") as operations:
        migration.downgrade()
    assert [call.args[0] for call in operations.drop_table.call_args_list] == [
        "interactions",
        "reviews",
    ]
    assert operations.drop_index.call_count == 2
    assert migration.revision == "0001" and migration.down_revision is None


@pytest.mark.parametrize("model", [Review, Interaction])
def test_models_use_uuid_timezone_and_postgresql_ddl(model):
    table = model.__table__
    sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    assert "UUID" in sql and "TIMESTAMP WITH TIME ZONE" in sql
    assert table.c.created_at.type.timezone is True
    assert table.c.id.default is not None
    assert table.c.movie_id.type.length == 128
    assert table.c.user_id.type.length == 128


def test_output_normalizes_timestamp_to_utc(review):
    review.created_at = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-3)))
    result = ReviewRead.model_validate(review)
    assert result.created_at == datetime(2026, 1, 1, 3, tzinfo=UTC)
    assert result.created_at.tzinfo is UTC


def test_output_rejects_naive_timestamps(review):
    review.created_at = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        ReviewRead.model_validate(review)
