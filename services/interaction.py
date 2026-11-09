from uuid import UUID

from pydantic import TypeAdapter

from domain.errors.reviews import ReviewNotFoundError
from domain.schemas.interactions import (
    InteractionToggle,
    InteractionToggleResponse,
    VisitorId,
)
from domain.schemas.reviews import ReviewCounts
from repositories.interaction import InteractionRepository
from repositories.review import ReviewRepository

_visitor_id = TypeAdapter(VisitorId)


class InteractionService:
    def __init__(
        self, reviews: ReviewRepository, interactions: InteractionRepository
    ) -> None:
        self.reviews = reviews
        self.interactions = interactions

    def toggle(
        self, review_id: UUID, payload: InteractionToggle, visitor_id: str
    ) -> InteractionToggleResponse:
        payload = InteractionToggle.model_validate(payload)
        visitor_id = _visitor_id.validate_python(visitor_id)
        if self.reviews.get(review_id) is None:
            raise ReviewNotFoundError()  # RN-04

        active = self.interactions.toggle(review_id, visitor_id, payload.type)

        # Contadores lidos depois do commit: refletem também votos de outros
        # visitantes gravados no mesmo instante.
        row = self.reviews.get_with_counts(review_id)
        if row is None:
            raise ReviewNotFoundError()
        marked = self.reviews.viewer_interactions([review_id], visitor_id)
        return InteractionToggleResponse(
            review_id=review_id,
            type=payload.type,
            active=active,
            counts=ReviewCounts(
                like=row.like, spoiler=row.spoiler, well_argued=row.well_argued
            ),
            viewer_interactions=sorted(marked.get(review_id, [])),
        )
