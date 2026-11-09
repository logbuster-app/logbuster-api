from decimal import Decimal
from unittest.mock import call
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, OperationalError

from domain.enums import ReviewInteractionType, ReviewSort
from domain.models.review import Review
from repositories.review import ReviewRepository, ReviewWithCounts

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


@pytest.mark.parametrize("method", ["get", "count", "rating", "list_with_counts"])
def test_query_failures_are_not_hidden(session, method):
    error = OperationalError("select", {}, Exception("Erro"))
    for name in ("get", "scalars", "scalar", "execute"):
        getattr(session, name).side_effect = error
    repository = ReviewRepository(session)
    with pytest.raises(OperationalError) as caught:
        if method == "list_with_counts":
            repository.list_with_counts(
                MOVIE_ID, sort=ReviewSort.WELL_ARGUED, limit=10, offset=0
            )
        else:
            getattr(repository, method)(uuid4() if method == "get" else MOVIE_ID)
    assert caught.value is error


ORDER_BY = {
    "well_argued": (
        "well_argued_count DESC, like_count DESC, "
        "reviews.created_at DESC, reviews.id DESC"
    ),
    "most_liked": (
        "like_count DESC, well_argued_count DESC, "
        "reviews.created_at DESC, reviews.id DESC"
    ),
    "newest": "reviews.created_at DESC, reviews.id DESC",
    "rating_desc": "reviews.rating DESC, reviews.created_at DESC, reviews.id DESC",
    "rating_asc": "reviews.rating ASC, reviews.created_at DESC, reviews.id DESC",
}


def compile_last_execute(session):
    statement = session.execute.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    return " ".join(str(compiled).split()), compiled.params


@pytest.mark.parametrize("sort", list(ReviewSort))
def test_list_orders_by_spec_criteria_in_sql(session, sort):
    session.execute.return_value = iter([])
    ReviewRepository(session).list_with_counts(MOVIE_ID, sort=sort, limit=10, offset=20)
    sql, params = compile_last_execute(session)
    assert f"ORDER BY {ORDER_BY[sort]} LIMIT" in sql
    assert params["param_1"] == 10 and params["param_2"] == 20


def test_list_aggregates_counts_of_the_movie_only(session):
    session.execute.return_value = iter([])
    ReviewRepository(session).list_with_counts(
        MOVIE_ID, sort=ReviewSort.WELL_ARGUED, limit=10, offset=0
    )
    sql, params = compile_last_execute(session)
    for index, alias in enumerate(['"like"', "spoiler", "well_argued"], start=1):
        assert (
            f"count(*) FILTER (WHERE review_interactions.type = %(type_{index})s) "
            f"AS {alias}"
        ) in sql
    assert "LEFT OUTER JOIN (SELECT review_interactions.review_id" in sql
    assert "GROUP BY review_interactions.review_id" in sql
    assert "coalesce(interaction_counts.well_argued, %(coalesce_3)s)" in sql
    # O filtro do filme vale na subquery e na consulta externa.
    assert sql.count("WHERE reviews.movie_id = %(movie_id_1)s") == 2
    assert params["movie_id_1"] == MOVIE_ID
    assert {params["type_1"], params["type_2"], params["type_3"]} == set(
        ReviewInteractionType
    )


def test_list_maps_rows_to_review_with_counts(session, review):
    session.execute.return_value = iter([(review, 4, 0, 9)])
    rows = ReviewRepository(session).list_with_counts(
        MOVIE_ID, sort=ReviewSort.NEWEST, limit=10, offset=0
    )
    assert rows == [ReviewWithCounts(review, like=4, spoiler=0, well_argued=9)]


def test_viewer_interactions_groups_by_review(session):
    first, second = uuid4(), uuid4()
    session.execute.return_value = iter(
        [
            (first, ReviewInteractionType.LIKE),
            (first, ReviewInteractionType.WELL_ARGUED),
            (second, ReviewInteractionType.SPOILER),
        ]
    )
    result = ReviewRepository(session).viewer_interactions([first, second], "v1")
    assert result == {
        first: [ReviewInteractionType.LIKE, ReviewInteractionType.WELL_ARGUED],
        second: [ReviewInteractionType.SPOILER],
    }
    sql, params = compile_last_execute(session)
    assert "review_interactions.review_id IN (__[POSTCOMPILE_review_id_1])" in sql
    assert "review_interactions.visitor_id = %(visitor_id_1)s" in sql
    assert params["visitor_id_1"] == "v1"
    assert params["review_id_1"] == [first, second]


def test_viewer_interactions_without_reviews_skips_query(session):
    assert ReviewRepository(session).viewer_interactions([], "v1") == {}
    session.execute.assert_not_called()
