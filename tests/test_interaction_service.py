from collections import Counter
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.enums import ReviewInteractionType
from domain.errors.reviews import ReviewNotFoundError
from domain.schemas.interactions import InteractionToggle
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository, ReviewWithCounts
from services.interaction import InteractionService

LIKE = ReviewInteractionType.LIKE
SPOILER = ReviewInteractionType.SPOILER
WELL_ARGUED = ReviewInteractionType.WELL_ARGUED


class InMemoryVotes:
    """Simula as duas tabelas para exercitar a regra de toggle de ponta a ponta."""

    def __init__(self, review):
        self.review = review
        self.votes: set[tuple] = set()
        self.reviews = Mock(spec=ReviewRepository)
        self.interactions = Mock(spec=InteractionRepository)
        self.reviews.get.side_effect = lambda rid: review if rid == review.id else None
        self.reviews.get_with_counts.side_effect = self._with_counts
        self.reviews.viewer_interactions.side_effect = self._viewer
        self.interactions.toggle.side_effect = self._toggle

    def _toggle(self, review_id, visitor_id, kind):
        vote = (review_id, visitor_id, kind)
        if vote in self.votes:
            self.votes.remove(vote)
            return False
        self.votes.add(vote)
        return True

    def _with_counts(self, review_id):
        counts = Counter(kind for rid, _v, kind in self.votes if rid == review_id)
        return ReviewWithCounts(
            self.review, counts[LIKE], counts[SPOILER], counts[WELL_ARGUED]
        )

    def _viewer(self, review_ids, visitor_id):
        marked = {}
        for rid, visitor, kind in self.votes:
            if rid in review_ids and visitor == visitor_id:
                marked.setdefault(rid, []).append(kind)
        return marked

    def service(self):
        return InteractionService(self.reviews, self.interactions)


def toggle(service, review, kind, visitor="V1"):
    return service.toggle(review.id, InteractionToggle(type=kind), visitor)


def test_first_click_adds_and_second_removes(review):
    """SPEC-BACK-06, cenário 1."""
    service = InMemoryVotes(review).service()

    first = toggle(service, review, WELL_ARGUED)
    second = toggle(service, review, WELL_ARGUED)

    assert (first.active, first.counts.well_argued) == (True, 1)
    assert first.viewer_interactions == [WELL_ARGUED]
    assert (second.active, second.counts.well_argued) == (False, 0)
    assert second.viewer_interactions == []
    assert first.review_id == review.id and first.type == WELL_ARGUED


def test_types_are_independent_per_visitor(review):
    service = InMemoryVotes(review).service()
    toggle(service, review, LIKE)
    result = toggle(service, review, WELL_ARGUED)
    assert result.counts.model_dump() == {"like": 1, "spoiler": 0, "well_argued": 1}
    assert result.viewer_interactions == [LIKE, WELL_ARGUED]


def test_multiple_visitors_accumulate_and_see_only_their_votes(review):
    service = InMemoryVotes(review).service()
    toggle(service, review, SPOILER, visitor="V1")
    toggle(service, review, SPOILER, visitor="V2")
    result = toggle(service, review, SPOILER, visitor="V3")
    assert result.counts.spoiler == 3
    removed = toggle(service, review, SPOILER, visitor="V2")
    assert (removed.active, removed.counts.spoiler) == (False, 2)
    assert removed.viewer_interactions == []


def test_missing_review_raises_404_without_voting(review):
    store = InMemoryVotes(review)
    with pytest.raises(ReviewNotFoundError):
        store.service().toggle(uuid4(), InteractionToggle(type=LIKE), "V1")
    store.interactions.toggle.assert_not_called()


def test_review_removed_after_toggle_raises_404(review):
    store = InMemoryVotes(review)
    store.reviews.get_with_counts.side_effect = None
    store.reviews.get_with_counts.return_value = None
    with pytest.raises(ReviewNotFoundError):
        toggle(store.service(), review, LIKE)


def test_visitor_id_is_normalized(review):
    store = InMemoryVotes(review)
    toggle(store.service(), review, LIKE, visitor="  V1  ")
    store.interactions.toggle.assert_called_once_with(review.id, "V1", LIKE)


@pytest.mark.parametrize("visitor", ["", "   ", "x" * 65])
def test_invalid_visitor_id_is_rejected_before_voting(review, visitor):
    store = InMemoryVotes(review)
    with pytest.raises(ValidationError):
        toggle(store.service(), review, LIKE, visitor=visitor)
    store.interactions.toggle.assert_not_called()


@pytest.mark.parametrize("kind", ["dislike", "LIKE", None])
def test_invalid_type_is_rejected_before_voting(review, kind):
    store = InMemoryVotes(review)
    payload = InteractionToggle.model_construct(type=kind)
    with pytest.raises(ValidationError):
        store.service().toggle(review.id, payload, "V1")
    store.interactions.toggle.assert_not_called()


def test_repository_failure_is_not_hidden(review):
    store = InMemoryVotes(review)
    error = RuntimeError("Falha de persistência")
    store.interactions.toggle.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        toggle(store.service(), review, LIKE)
    assert caught.value is error
