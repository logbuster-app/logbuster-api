from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import call
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from domain.errors.movies import DuplicateReviewError
from domain.models.review import Review
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository


@pytest.mark.parametrize(
    "repository_class,fixture_name",
    [(ReviewRepository, "review"), (InteractionRepository, "interaction")],
)
def test_create_persists_before_returning(
    session, request, repository_class, fixture_name
):
    entity = request.getfixturevalue(fixture_name)
    assert repository_class(session).create(entity) is entity
    assert session.mock_calls == [
        call.add(entity),
        call.flush(),
        call.refresh(entity),
        call.commit(),
    ]


@pytest.mark.parametrize("stage", ["flush", "commit"])
def test_duplicate_constraint_is_converted_even_on_commit(session, review, stage):
    original = Exception("Não analisar texto do erro")
    original.sqlstate = "23505"
    original.diag = SimpleNamespace(constraint_name="uq_reviews_movie_user")
    getattr(session, stage).side_effect = IntegrityError("insert", {}, original)
    with pytest.raises(DuplicateReviewError):
        ReviewRepository(session).create(review)
    session.rollback.assert_called_once()


@pytest.mark.parametrize(
    "code,constraint", [("23514", "ck_reviews_rating"), ("23505", "reviews_pkey")]
)
def test_other_integrity_errors_are_not_duplicate_reviews(
    session, review, code, constraint
):
    original = Exception("Erro")
    original.sqlstate = code
    original.diag = SimpleNamespace(constraint_name=constraint)
    error = IntegrityError("insert", {}, original)
    session.flush.side_effect = error
    with pytest.raises(IntegrityError) as caught:
        ReviewRepository(session).create(review)
    assert caught.value is error
    session.rollback.assert_called_once()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "repository_class,fixture_name",
    [(ReviewRepository, "review"), (InteractionRepository, "interaction")],
)
@pytest.mark.parametrize("stage", ["flush", "refresh", "commit"])
def test_create_rolls_back_on_failure(
    session, request, repository_class, fixture_name, stage
):
    error = OperationalError("insert", {}, Exception("Erro"))
    getattr(session, stage).side_effect = error
    with pytest.raises(OperationalError):
        repository_class(session).create(request.getfixturevalue(fixture_name))
    session.rollback.assert_called_once()


def test_get_uses_primary_key(session, review):
    session.get.return_value = review
    assert ReviewRepository(session).get(review.id) is review
    session.get.assert_called_once_with(Review, review.id)


def test_get_missing_returns_none(session):
    session.get.return_value = None
    assert ReviewRepository(session).get(uuid4()) is None


def test_list_filters_orders_and_paginates_in_sql(session, review):
    session.scalars.return_value = iter([review])
    result = ReviewRepository(session).list("catalog:42", limit=2, offset=4)
    statement = session.scalars.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert result == [review]
    assert "WHERE reviews.movie_id =" in sql
    assert "ORDER BY reviews.created_at DESC, reviews.id DESC" in sql
    assert "LIMIT" in sql and "OFFSET" in sql
    assert compiled.params == {"movie_id_1": "catalog:42", "param_1": 2, "param_2": 4}


@pytest.mark.parametrize("count", [0, 5])
def test_count_filters_movie(session, count):
    session.scalar.return_value = count
    assert ReviewRepository(session).count("catalog:42") == count
    compiled = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "count(reviews.id)" in str(compiled)
    assert compiled.params == {"movie_id_1": "catalog:42"}


@pytest.mark.parametrize("row", [(Decimal("4.5"), 2), (None, 0)])
def test_rating_aggregates_in_database(session, row):
    session.execute.return_value.one.return_value = row
    assert ReviewRepository(session).rating("catalog:42") == row
    compiled = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "avg(reviews.rating)" in str(compiled)
    assert "count(reviews.id)" in str(compiled)
    assert "WHERE reviews.movie_id =" in str(compiled)
    assert compiled.params == {"movie_id_1": "catalog:42"}
    session.scalars.assert_not_called()


@pytest.mark.parametrize("method", ["get", "list", "count", "rating"])
def test_query_failures_are_not_hidden(session, method):
    error = OperationalError("select", {}, Exception("Erro"))
    for name in ("get", "scalars", "scalar", "execute"):
        getattr(session, name).side_effect = error
    repository = ReviewRepository(session)
    with pytest.raises(OperationalError) as caught:
        if method == "list":
            repository.list("catalog:42", limit=20, offset=0)
        else:
            getattr(repository, method)(uuid4() if method == "get" else "catalog:42")
    assert caught.value is error
