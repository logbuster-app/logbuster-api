from datetime import UTC, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from domain.enums import ReviewSummaryStatus


class ReviewSummaryResponse(BaseModel):
    """Bloco "Resumo da comunidade" (SPEC-BACK-09, §4).

    `text` e `generated_at` só vêm preenchidos em `ready`. O front oculta o
    bloco em `insufficient_reviews` e mostra uma mensagem simples em
    `unavailable`, sempre com o aviso "Gerado por IA" junto do texto.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "status": "ready",
                    "text": (
                        "A comunidade destaca a direção e a trilha sonora do filme."
                    ),
                    "generated_at": "2026-11-23T15:00:00Z",
                }
            ]
        }
    )

    status: ReviewSummaryStatus
    text: str | None = None
    generated_at: AwareDatetime | None = None

    @field_validator("generated_at")
    @classmethod
    def timestamp_in_utc(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(UTC) if value is not None else None

    @classmethod
    def ready(cls, text: str, generated_at: datetime) -> Self:
        return cls(
            status=ReviewSummaryStatus.READY, text=text, generated_at=generated_at
        )

    @classmethod
    def insufficient(cls) -> Self:
        return cls(status=ReviewSummaryStatus.INSUFFICIENT_REVIEWS)

    @classmethod
    def unavailable(cls) -> Self:
        return cls(status=ReviewSummaryStatus.UNAVAILABLE)
