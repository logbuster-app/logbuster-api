from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.errors.movies import DuplicateReviewError, ReviewNotFoundError
from domain.schemas.movies import ReviewCreate
from services.review import ReviewService


def test_create_review_runs_business_logic(review_repository, review):
    review_repository.create.return_value = review
    payload = ReviewCreate(user_id="user-1", rating=5, comment=review.comment)

    result = ReviewService(review_repository).create("catalog:42", payload)

    saved = review_repository.create.call_args.args[0]
    assert (saved.movie_id, saved.user_id, saved.rating, saved.comment) == (
        "catalog:42",
        "user-1",
        5,
        review.comment,
    )
    assert result.id == review.id
    assert result.created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("rating", [0, 6, -1, 1.5, True, "5", None])
def test_service_rejects_invalid_rating_before_persisting(review_repository, rating):
    payload = ReviewCreate.model_construct(user_id="user-1", rating=rating)
    with pytest.raises(ValidationError):
        ReviewService(review_repository).create("catalog:42", payload)
    review_repository.create.assert_not_called()


@pytest.mark.parametrize("rating", [1, 5])
def test_service_accepts_rating_boundaries(review_repository, review, rating):
    review.rating = rating
    review_repository.create.return_value = review
    result = ReviewService(review_repository).create(
        review.movie_id, ReviewCreate(user_id=review.user_id, rating=rating)
    )
    assert result.rating == rating


def test_duplicate_review_conflict_is_preserved(review_repository):
    review_repository.create.side_effect = DuplicateReviewError()
    with pytest.raises(DuplicateReviewError):
        ReviewService(review_repository).create(
            "catalog:42", ReviewCreate(user_id="user-1", rating=3)
        )
    review_repository.create.assert_called_once()


def test_list_reviews_uses_repository_pagination(review_repository, review):
    review_repository.list.return_value = [review]
    review_repository.count.return_value = 7
    result = ReviewService(review_repository).list("catalog:42", limit=2, offset=4)
    review_repository.list.assert_called_once_with("catalog:42", limit=2, offset=4)
    review_repository.count.assert_called_once_with("catalog:42")
    assert (len(result.items), result.total, result.limit, result.offset) == (
        1,
        7,
        2,
        4,
    )


def test_list_reviews_empty(review_repository):
    review_repository.list.return_value = []
    review_repository.count.return_value = 0
    assert ReviewService(review_repository).list("unknown").model_dump() == {
        "items": [],
        "total": 0,
        "limit": 20,
        "offset": 0,
    }


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (20, -1)])
def test_service_validates_pagination(review_repository, limit, offset):
    with pytest.raises(ValidationError):
        ReviewService(review_repository).list("catalog:42", limit=limit, offset=offset)
    review_repository.list.assert_not_called()


def test_get_review(review_repository, review):
    review_repository.get.return_value = review
    assert ReviewService(review_repository).get(review.id).id == review.id
    review_repository.get.assert_called_once_with(review.id)


def test_get_missing_review(review_repository):
    review_repository.get.return_value = None
    with pytest.raises(ReviewNotFoundError):
        ReviewService(review_repository).get(uuid4())


@pytest.mark.parametrize(
    "average,count,expected",
    [
        (Decimal("3.6666666667"), 3, 3.67),
        (Decimal("4.125"), 8, 4.13),
        (Decimal("5"), 1, 5.0),
        (None, 0, None),
    ],
)
def test_rating_rounding_and_empty_movie(review_repository, average, count, expected):
    review_repository.rating.return_value = (average, count)
    result = ReviewService(review_repository).rating("catalog:42")
    assert result.movie_id == "catalog:42"
    assert result.average_rating == expected
    assert result.reviews_count == count
    review_repository.rating.assert_called_once_with("catalog:42")


@pytest.mark.parametrize("movie_id", ["", "   ", "x" * 129])
def test_invalid_movie_identifier(review_repository, movie_id):
    with pytest.raises(ValidationError):
        ReviewService(review_repository).rating(movie_id)
    review_repository.rating.assert_not_called()


def test_service_does_not_swallow_repository_failures(review_repository):
    error = RuntimeError("Falha de persistência")
    review_repository.list.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        ReviewService(review_repository).list("catalog:42")
    assert caught.value is error


def test_identifier_is_normalized(review_repository, review):
    review_repository.create.return_value = review
    ReviewService(review_repository).create(
        " catalog:42 ", ReviewCreate(user_id=" user-1 ", rating=5)
    )
    saved = review_repository.create.call_args.args[0]
    assert (saved.movie_id, saved.user_id) == ("catalog:42", "user-1")
