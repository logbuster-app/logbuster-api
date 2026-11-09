from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.enums import Highlight, ReviewInteractionType, ReviewSort
from domain.models.review import Review
from domain.schemas.reviews import ReviewCreate, ReviewResponse
from repositories.review import ReviewWithCounts
from services.review import ReviewService

MOVIE_ID = "tt0133093"


def test_create_review_runs_business_logic(review_repository, review, review_payload):
    review_repository.create.return_value = review

    result = ReviewService(review_repository).create(ReviewCreate(**review_payload))

    saved = review_repository.create.call_args.args[0]
    assert saved.movie_id == MOVIE_ID
    assert saved.author_name == "Thyago"
    assert saved.rating == Decimal("4.5") and isinstance(saved.rating, Decimal)
    assert saved.content == review_payload["content"]
    assert saved.is_spoiler is False
    assert saved.highlights == ["direction", "visual_effects"]
    assert isinstance(result, ReviewResponse)
    assert result.id == review.id
    assert result.counts.model_dump() == {"like": 0, "spoiler": 0, "well_argued": 0}
    assert result.viewer_interactions == []
    assert result.created_at.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("rating", [0.5, 1, 4.5, 5.0])
def test_rating_is_stored_as_exact_decimal(
    review_repository, review, review_payload, rating
):
    review.rating = Decimal(str(rating))
    review_repository.create.return_value = review
    result = ReviewService(review_repository).create(
        ReviewCreate(**{**review_payload, "rating": rating})
    )
    assert review_repository.create.call_args.args[0].rating == Decimal(str(rating))
    assert result.rating == rating


def test_text_fields_are_normalized(review_repository, review, review_payload):
    review_repository.create.return_value = review
    payload = {
        **review_payload,
        "movie_id": f" {MOVIE_ID} ",
        "author_name": "  Thyago  ",
        "content": f"  {review_payload['content']}  ",
    }
    ReviewService(review_repository).create(ReviewCreate(**payload))
    saved = review_repository.create.call_args.args[0]
    assert (saved.movie_id, saved.author_name, saved.content) == (
        MOVIE_ID,
        "Thyago",
        review_payload["content"],
    )


def test_highlights_default_to_empty(review_repository, review, review_payload):
    review.highlights = []
    review_repository.create.return_value = review
    payload = {k: v for k, v in review_payload.items() if k != "highlights"}
    result = ReviewService(review_repository).create(ReviewCreate(**payload))
    assert review_repository.create.call_args.args[0].highlights == []
    assert result.highlights == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("rating", 4.3),
        ("rating", 0),
        ("highlights", [Highlight.ACTING] * 2),
        ("movie_id", "catalog:42"),
    ],
)
def test_service_revalidates_before_persisting(
    review_repository, review_payload, field, value
):
    payload = ReviewCreate.model_construct(**{**review_payload, field: value})
    with pytest.raises(ValidationError):
        ReviewService(review_repository).create(payload)
    review_repository.create.assert_not_called()


def test_service_does_not_swallow_repository_failures(
    review_repository, review_payload
):
    error = RuntimeError("Falha de persistência")
    review_repository.create.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        ReviewService(review_repository).create(ReviewCreate(**review_payload))
    assert caught.value is error


@pytest.mark.parametrize(
    "average,count,expected",
    [
        (Decimal("3.6666666667"), 3, 3.67),
        (Decimal("4.125"), 8, 4.13),
        (Decimal("0.5"), 1, 0.5),
        (Decimal("5"), 1, 5.0),
        (None, 0, None),
    ],
)
def test_rating_rounding_and_empty_movie(review_repository, average, count, expected):
    review_repository.rating.return_value = (average, count)
    result = ReviewService(review_repository).rating(MOVIE_ID)
    assert result.movie_id == MOVIE_ID
    assert result.average_rating == expected
    assert result.reviews_count == count
    review_repository.rating.assert_called_once_with(MOVIE_ID)


@pytest.mark.parametrize("movie_id", ["", "   ", "x" * 129])
def test_invalid_movie_identifier(review_repository, movie_id):
    with pytest.raises(ValidationError):
        ReviewService(review_repository).rating(movie_id)
    review_repository.rating.assert_not_called()


def row(review, like=0, spoiler=0, well_argued=0):
    return ReviewWithCounts(review, like, spoiler, well_argued)


def test_list_uses_default_sort_and_pagination(review_repository, review):
    review_repository.list_with_counts.return_value = [row(review, 4, 1, 9)]
    review_repository.count.return_value = 1

    result = ReviewService(review_repository).list(MOVIE_ID)

    review_repository.list_with_counts.assert_called_once_with(
        MOVIE_ID, sort=ReviewSort.WELL_ARGUED, limit=10, offset=0
    )
    review_repository.count.assert_called_once_with(MOVIE_ID)
    review_repository.viewer_interactions.assert_not_called()
    assert (result.total, result.page, result.page_size, result.sort) == (
        1,
        1,
        10,
        ReviewSort.WELL_ARGUED,
    )
    (item,) = result.items
    assert item.id == review.id
    assert item.counts.model_dump() == {"like": 4, "spoiler": 1, "well_argued": 9}
    assert item.viewer_interactions == []


@pytest.mark.parametrize(
    "page,page_size,offset", [(1, 10, 0), (2, 10, 10), (3, 25, 50), (1, 50, 0)]
)
def test_list_converts_page_to_offset(review_repository, page, page_size, offset):
    review_repository.list_with_counts.return_value = []
    review_repository.count.return_value = 0
    ReviewService(review_repository).list(
        MOVIE_ID, sort=ReviewSort.NEWEST, page=page, page_size=page_size
    )
    review_repository.list_with_counts.assert_called_once_with(
        MOVIE_ID, sort=ReviewSort.NEWEST, limit=page_size, offset=offset
    )


def test_list_preserves_repository_order(review_repository, review):
    first = review
    second = Review(**{**_columns(review), "id": uuid4()})
    third = Review(**{**_columns(review), "id": uuid4()})
    review_repository.list_with_counts.return_value = [
        row(second, well_argued=8),
        row(third, well_argued=3),
        row(first, well_argued=1),
    ]
    review_repository.count.return_value = 3
    result = ReviewService(review_repository).list(MOVIE_ID)
    assert [item.counts.well_argued for item in result.items] == [8, 3, 1]
    assert [item.id for item in result.items] == [second.id, third.id, first.id]


def test_list_empty_movie_returns_empty_page(review_repository):
    review_repository.list_with_counts.return_value = []
    review_repository.count.return_value = 0
    result = ReviewService(review_repository).list(MOVIE_ID, visitor_id="v1")
    assert result.model_dump() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "sort": "well_argued",
    }
    review_repository.viewer_interactions.assert_not_called()


def test_list_fills_viewer_interactions_with_visitor(review_repository, review):
    other = Review(**{**_columns(review), "id": uuid4()})
    review_repository.list_with_counts.return_value = [row(review), row(other)]
    review_repository.count.return_value = 2
    review_repository.viewer_interactions.return_value = {
        review.id: [ReviewInteractionType.WELL_ARGUED, ReviewInteractionType.LIKE]
    }

    result = ReviewService(review_repository).list(MOVIE_ID, visitor_id="v1")

    review_repository.viewer_interactions.assert_called_once_with(
        [review.id, other.id], "v1"
    )
    assert result.items[0].viewer_interactions == ["like", "well_argued"]
    assert result.items[1].viewer_interactions == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 51},
        {"sort": "oldest"},
        {"movie_id": "catalog:42"},
    ],
)
def test_list_validates_parameters(review_repository, kwargs):
    params = {"movie_id": MOVIE_ID, **kwargs}
    movie_id = params.pop("movie_id")
    with pytest.raises(ValidationError):
        ReviewService(review_repository).list(movie_id, **params)
    review_repository.list_with_counts.assert_not_called()


def _columns(review):
    return {
        column.key: getattr(review, column.key) for column in Review.__table__.columns
    }
