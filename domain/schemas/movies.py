from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from domain.enums import InteractionType

Identifier = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")

    user_id: Identifier
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    comment: Annotated[str | None, Field(max_length=2000)] = None


class InteractionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always")

    user_id: Identifier
    interaction_type: InteractionType


class PublicRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movie_id: Identifier
    user_id: Identifier
    created_at: AwareDatetime

    @field_validator("created_at")
    @classmethod
    def timestamp_in_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class ReviewRead(PublicRecord):
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    comment: Annotated[str | None, Field(max_length=2000)]


class ReviewPage(BaseModel):
    items: list[ReviewRead]
    total: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0)] = 0


class PaginationParams(BaseModel):
    limit: Annotated[int, Field(ge=1, le=100)] = 20
    offset: Annotated[int, Field(ge=0)] = 0


class MovieRating(BaseModel):
    movie_id: Identifier
    average_rating: Annotated[
        float | None,
        Field(
            ge=1,
            le=5,
            description="Média arredondada a duas casas decimais; null sem avaliações.",
        ),
    ]
    reviews_count: Annotated[int, Field(ge=0)]


class InteractionRead(PublicRecord):
    interaction_type: InteractionType


class ErrorResponse(BaseModel):
    detail: str
