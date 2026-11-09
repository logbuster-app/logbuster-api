from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from domain.enums import ReviewInteractionType
from domain.schemas.reviews import ReviewCounts

VisitorId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]


class InteractionToggle(BaseModel):
    """Corpo de `POST /api/v1/reviews/{review_id}/interactions` (SPEC-BACK-06)."""

    model_config = ConfigDict(
        extra="forbid",
        revalidate_instances="always",
        json_schema_extra={"examples": [{"type": "well_argued"}]},
    )

    type: ReviewInteractionType


class InteractionToggleResponse(BaseModel):
    review_id: UUID
    type: ReviewInteractionType
    active: bool
    counts: ReviewCounts
    viewer_interactions: list[ReviewInteractionType]
