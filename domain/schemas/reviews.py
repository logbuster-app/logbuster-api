from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from domain.enums import Highlight, ReviewInteractionType
from domain.models.review import Review
from domain.schemas.movies import ImdbId

MAX_HIGHLIGHTS = 2

Rating = Annotated[
    float,
    Field(
        strict=True,
        ge=0.5,
        le=5.0,
        multiple_of=0.5,
        description="Estrelas de 0.5 a 5.0, em passos de 0.5.",
        examples=[4.5],
    ),
]
AuthorName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=50)
]
Content = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
]


class ReviewCreate(BaseModel):
    """Payload de `POST /api/v1/reviews` (SPEC-BACK-01)."""

    model_config = ConfigDict(
        extra="forbid",
        revalidate_instances="always",
        json_schema_extra={
            "examples": [
                {
                    "movie_id": "tt0133093",
                    "author_name": "Thyago",
                    "rating": 4.5,
                    "content": (
                        "Direção precisa e efeitos visuais que revolucionaram o gênero."
                    ),
                    "is_spoiler": False,
                    "highlights": ["direction", "visual_effects"],
                }
            ]
        },
    )

    movie_id: ImdbId
    author_name: AuthorName
    rating: Rating
    content: Content
    is_spoiler: Annotated[bool, Field(strict=True)] = False
    highlights: Annotated[
        list[Highlight], Field(max_length=MAX_HIGHLIGHTS, default_factory=list)
    ]

    @field_validator("highlights")
    @classmethod
    def unique_highlights(cls, value: list[Highlight]) -> list[Highlight]:
        if len(set(value)) != len(value):
            raise ValueError("Os destaques não podem se repetir.")
        return value


class ReviewCounts(BaseModel):
    like: Annotated[int, Field(ge=0)] = 0
    spoiler: Annotated[int, Field(ge=0)] = 0
    well_argued: Annotated[int, Field(ge=0)] = 0


class ReviewResponse(BaseModel):
    """Item de avaliação comum a BACK-01, BACK-02 e BACK-03."""

    id: UUID
    movie_id: str
    author_name: str
    rating: Annotated[float, Field(ge=0.5, le=5.0, multiple_of=0.5)]
    content: str
    is_spoiler: bool
    highlights: list[Highlight]
    counts: ReviewCounts
    viewer_interactions: list[ReviewInteractionType]
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def timestamp_in_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)

    @classmethod
    def from_model(
        cls,
        review: Review,
        counts: ReviewCounts | None = None,
        viewer_interactions: Iterable[ReviewInteractionType] = (),
    ) -> Self:
        return cls(
            id=review.id,
            movie_id=review.movie_id,
            author_name=review.author_name,
            rating=float(review.rating),
            content=review.content,
            is_spoiler=review.is_spoiler,
            highlights=review.highlights,
            counts=counts or ReviewCounts(),
            viewer_interactions=sorted(viewer_interactions),
            created_at=review.created_at,
        )
