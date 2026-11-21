"""Resumo da comunidade gerado por IA, em cache por filme (SPEC-BACK-09).

Fluxo de `get`:

1. Menos de `MIN_REVIEWS` avaliações → `insufficient_reviews`, sem IA.
2. Resumo em cache servível → `ready` com o texto e a data da geração.
   Deixa de ser servível quando chegam `regen_threshold` avaliações novas ou
   quando alguma avaliação usada nele passa a ser spoiler (3 votos).
3. Sem cache servível: tenta a trava do filme e gera com as avaliações
   elegíveis. Sem texto elegível, falha, demora ou resposta imprópria
   → `unavailable`, sem expor texto antigo. Falhas ficam registradas para
   não chamar a IA de novo antes de `retry_after_seconds`.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from domain.enums import SpoilerCheckStatus
from domain.schemas.ai import ReviewSummaryResponse
from services.ai import AIUnavailableError, ChatClient
from services.ai_prompts import (
    MAX_SUMMARY_REVIEWS,
    SummaryInput,
    clean_summary,
    select_for_summary,
    summary_messages,
)

if TYPE_CHECKING:
    from domain.models.review_summary import ReviewSummary
    from repositories.review import ReviewRepository
    from repositories.review_summary import ReviewSummaryRepository

MIN_REVIEWS = 3
SUMMARY_MAX_TOKENS = 4096
SUMMARY_TEMPERATURE = 0.3

TitleLookup = Callable[[str], str | None]
SpoilerChecker = Callable[[str, str], SpoilerCheckStatus]


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ReviewSummaryService:
    def __init__(
        self,
        reviews: "ReviewRepository",
        summaries: "ReviewSummaryRepository",
        chat: ChatClient,
        *,
        title_lookup: TitleLookup,
        spoiler_checker: SpoilerChecker,
        regen_threshold: int,
        retry_after_seconds: int,
        timeout: float,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.reviews = reviews
        self.summaries = summaries
        self.chat = chat
        self.title_lookup = title_lookup
        self.spoiler_checker = spoiler_checker
        self.regen_threshold = regen_threshold
        self.retry_after = timedelta(seconds=retry_after_seconds)
        self.timeout = timeout
        self.now = now

    def get(self, movie_id: str) -> ReviewSummaryResponse:
        total = self.reviews.count(movie_id)
        if total < MIN_REVIEWS:
            return ReviewSummaryResponse.insufficient()

        cached = self.summaries.get(movie_id)
        if self._servable(cached, total):
            return self._ready(cached)
        if not self.chat.configured or self._cooling_down(cached):
            return ReviewSummaryResponse.unavailable()

        # Outra requisição já está gerando o resumo deste filme.
        if not self.summaries.try_lock(movie_id):
            return ReviewSummaryResponse.unavailable()

        # Com a trava, relê: a geração concorrente pode ter acabado agora.
        cached = self.summaries.get(movie_id, refresh=True)
        if self._servable(cached, total):
            response = self._ready(cached)
            self.summaries.release()
            return response
        if self._cooling_down(cached):
            self.summaries.release()
            return ReviewSummaryResponse.unavailable()
        return self._generate(movie_id, total)

    def _servable(self, cached: "ReviewSummary | None", total: int) -> bool:
        if cached is None or not cached.text or cached.generated_at is None:
            return False
        if total - cached.reviews_count >= self.regen_threshold:
            return False
        sources = set(cached.source_review_ids or [])
        return self.reviews.eligible_ids(list(sources)) == sources

    def _cooling_down(self, cached: "ReviewSummary | None") -> bool:
        return (
            cached is not None
            and cached.failed_at is not None
            and self.now() - cached.failed_at < self.retry_after
        )

    @staticmethod
    def _ready(cached: "ReviewSummary") -> ReviewSummaryResponse:
        return ReviewSummaryResponse.ready(cached.text, cached.generated_at)

    def _generate(self, movie_id: str, total: int) -> ReviewSummaryResponse:
        rows = self.reviews.summary_candidates(movie_id, limit=MAX_SUMMARY_REVIEWS)
        selected = select_for_summary(
            [
                SummaryInput(
                    rating=float(row.review.rating),
                    highlights=row.review.highlights,
                    content=row.review.content,
                )
                for row in rows
            ]
        )
        if not selected:
            # Só há avaliações com spoiler: nada elegível para resumir.
            self.summaries.release()
            return ReviewSummaryResponse.unavailable()

        messages = summary_messages(movie_id, selected, self.title_lookup(movie_id))
        try:
            answer = self.chat.complete(
                messages,
                max_tokens=SUMMARY_MAX_TOKENS,
                timeout=self.timeout,
                temperature=SUMMARY_TEMPERATURE,
            )
        except AIUnavailableError:
            return self._fail(movie_id)

        text = clean_summary(answer)
        # Segunda barreira contra spoiler: o próprio resumo passa pela análise.
        if (
            text is None
            or self.spoiler_checker(movie_id, text) == SpoilerCheckStatus.SUSPECTED
        ):
            return self._fail(movie_id)

        generated_at = self.now()
        self.summaries.save_success(
            movie_id,
            text=text,
            generated_at=generated_at,
            reviews_count=total,
            source_review_ids=[row.review.id for row in rows[: len(selected)]],
        )
        return ReviewSummaryResponse.ready(text, generated_at)

    def _fail(self, movie_id: str) -> ReviewSummaryResponse:
        self.summaries.save_failure(movie_id, failed_at=self.now())
        return ReviewSummaryResponse.unavailable()
