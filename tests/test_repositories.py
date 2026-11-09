from decimal import Decimal
from unittest.mock import call
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from domain.models.review import Review
from repositories.review import ReviewRepository

MOVIE_ID = "tt0133093"


def test_create_persists_before_returning(session, review):
    assert ReviewRepository(session).create(review) is review
    assert session.mock_calls == [
        call.add(review),
        call.flush(),
        call.refresh(review),
        call.commit(),
    ]


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("insert", {}, Exception("Erro")),
        IntegrityError("insert", {}, Exception("ck_reviews_rating")),
    ],
)
@pytest.mark.parametrize("stage", ["flush", "refresh", "commit"])
def test_create_rolls_back_and_propagates_failures(session, review, stage, error):
    getattr(session, stage).side_effect = error
    with pytest.raises(type(error)) as caught:
        ReviewRepository(session).create(review)
    assert caught.value is error
    session.rollback.assert_called_once()


def test_get_uses_primary_key(session, review):
    session.get.return_value = review
    assert ReviewRepository(session).get(review.id) is review
    session.get.assert_called_once_with(Review, review.id)


def test_get_missing_returns_none(session):
    session.get.return_value = None
    assert ReviewRepository(session).get(uuid4()) is None


@pytest.mark.parametrize("count", [0, 5])
def test_count_filters_movie(session, count):
    session.scalar.return_value = count
    assert ReviewRepository(session).count(MOVIE_ID) == count
    compiled = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "count(reviews.id)" in str(compiled)
    assert compiled.params == {"movie_id_1": MOVIE_ID}


@pytest.mark.parametrize("row", [(Decimal("4.5"), 2), (None, 0)])
def test_rating_aggregates_in_database(session, row):
    session.execute.return_value.one.return_value = row
    assert ReviewRepository(session).rating(MOVIE_ID) == row
    compiled = session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "avg(reviews.rating)" in str(compiled)
    assert "count(reviews.id)" in str(compiled)
    assert "WHERE reviews.movie_id =" in str(compiled)
    assert compiled.params == {"movie_id_1": MOVIE_ID}
    session.scalars.assert_not_called()


@pytest.mark.parametrize("method", ["get", "count", "rating"])
def test_query_failures_are_not_hidden(session, method):
    error = OperationalError("select", {}, Exception("Erro"))
    for name in ("get", "scalars", "scalar", "execute"):
        getattr(session, name).side_effect = error
    repository = ReviewRepository(session)
    with pytest.raises(OperationalError) as caught:
        getattr(repository, method)(uuid4() if method == "get" else MOVIE_ID)
    assert caught.value is error
