from datetime import UTC, datetime
from unittest.mock import call
from uuid import uuid4

import pytest
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import OperationalError

from domain.models.review_summary import ReviewSummary
from repositories.review import ReviewRepository, ReviewWithCounts
from repositories.review_summary import ReviewSummaryRepository

MOVIE_ID = "tt0133093"
NOW = datetime(2026, 11, 23, 15, tzinfo=UTC)


def plain_sql(statement):
    return " ".join(str(statement.compile(dialect=sqlite.dialect())).split())


def sql(statement):
    compiled = statement.compile(
        dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}
    )
    return " ".join(str(compiled).split())


def test_summary_candidates_exclude_author_and_community_spoilers(session, review):
    session.execute.return_value = [(review, 1, 2, 3)]

    rows = ReviewRepository(session).summary_candidates(MOVIE_ID, limit=30)

    assert rows == [ReviewWithCounts(review, 1, 2, 3)]
    query = sql(session.execute.call_args.args[0])
    assert f"reviews.movie_id = '{MOVIE_ID}'" in query
    assert "reviews.is_spoiler IS 0" in query
    assert "coalesce(interaction_counts.spoiler, 0) < 10" in query
    assert "ORDER BY well_argued_count DESC" in query
    assert "LIMIT 30" in query


def test_eligible_ids_skips_query_without_ids(session):
    assert ReviewRepository(session).eligible_ids([]) == set()
    session.execute.assert_not_called()


def test_eligible_ids_returns_still_eligible_reviews(session, review):
    session.execute.return_value = [(review, 0, 0, 0)]

    result = ReviewRepository(session).eligible_ids([review.id, uuid4()])

    assert result == {review.id}
    query = plain_sql(session.execute.call_args.args[0])
    assert "reviews.is_spoiler IS 0" in query
    assert "reviews.id IN" in query
    assert "coalesce(interaction_counts.spoiler" in query


def test_rows_for_author_filters_account(session, review):
    user_id = uuid4()
    session.execute.return_value = [(review, 0, 1, 2)]

    assert ReviewRepository(session).rows_for_author(user_id) == [
        ReviewWithCounts(review, 0, 1, 2)
    ]
    assert "reviews.user_id" in plain_sql(session.execute.call_args.args[0])


@pytest.mark.parametrize("refresh", [False, True])
def test_summary_get_by_primary_key(session, refresh):
    ReviewSummaryRepository(session).get(MOVIE_ID, refresh=refresh)
    session.get.assert_called_once_with(
        ReviewSummary, MOVIE_ID, populate_existing=refresh
    )


def test_try_lock_prevents_concurrent_generation_until_released(session):
    repo_one = ReviewSummaryRepository(session)
    repo_two = ReviewSummaryRepository(session)
    try:
        assert repo_one.try_lock(MOVIE_ID) is True
        assert repo_two.try_lock(MOVIE_ID) is False
    finally:
        repo_one.release()
    assert repo_two.try_lock(MOVIE_ID) is True
    repo_two.release()


def test_release_rolls_back(session):
    ReviewSummaryRepository(session).release()
    assert session.mock_calls == [call.rollback()]


def test_save_success_upserts_and_clears_failure(session):
    source = uuid4()

    ReviewSummaryRepository(session).save_success(
        MOVIE_ID,
        text="Resumo.",
        generated_at=NOW,
        reviews_count=4,
        source_review_ids=[source],
    )

    statement = session.execute.call_args.args[0]
    query = plain_sql(statement)
    assert "ON CONFLICT (movie_id) DO UPDATE SET" in query
    for column in (
        "text",
        "generated_at",
        "reviews_count",
        "source_review_ids",
        "failed_at",
    ):
        assert f"{column} = excluded.{column}" in query
    params = statement.compile().params
    assert params["text"] == "Resumo."
    assert params["reviews_count"] == 4
    assert params["source_review_ids"] == [source]
    assert params["failed_at"] is None
    session.commit.assert_called_once()


def test_save_failure_only_touches_failed_at(session):
    ReviewSummaryRepository(session).save_failure(MOVIE_ID, failed_at=NOW)

    query = plain_sql(session.execute.call_args.args[0])
    assert "DO UPDATE SET failed_at = excluded.failed_at" in query
    assert "text = excluded.text" not in query
    session.commit.assert_called_once()


def test_save_rolls_back_and_propagates_failures(session):
    error = OperationalError("insert", {}, Exception("falha"))
    session.execute.side_effect = error

    with pytest.raises(OperationalError):
        ReviewSummaryRepository(session).save_failure(MOVIE_ID, failed_at=NOW)
    session.rollback.assert_called_once()


# --- CR-02 ------------------------------------------------------------------


@pytest.mark.parametrize(("rowcount", "expected"), [(1, True), (0, False)])
def test_mark_spoiler_only_turns_flag_on(session, rowcount, expected):
    session.execute.return_value.rowcount = rowcount
    review_id = uuid4()

    assert ReviewRepository(session).mark_spoiler(review_id) is expected

    query = plain_sql(session.execute.call_args.args[0])
    assert query.startswith("UPDATE reviews SET is_spoiler=")
    assert "WHERE reviews.id = " in query
    assert "reviews.is_spoiler IS 0" in query
    session.commit.assert_called_once()


def test_mark_spoiler_rolls_back_on_failure(session):
    session.execute.side_effect = OperationalError("update", {}, Exception("falha"))

    with pytest.raises(OperationalError):
        ReviewRepository(session).mark_spoiler(uuid4())
    session.rollback.assert_called_once()
