from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.enums import Highlight
from domain.schemas.reviews import ReviewCreate, ReviewResponse
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
