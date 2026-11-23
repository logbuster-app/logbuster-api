"""Análise de spoiler pela IA (SPEC-BACK-09 com o CR-02).

Depois do CR-02, quem usa este serviço é o agendador pós-publicação
(`services/spoiler_scheduler.py`) e a segunda barreira do resumo da
comunidade. Qualquer falha da IA responde `unavailable`, que não muda nada.
"""

from collections.abc import Callable
from dataclasses import dataclass

from domain.enums import SpoilerCheckStatus
from services.ai import AIUnavailableError, ChatClient
from services.ai_prompts import parse_spoiler_answer, spoiler_check_messages
from services.movie_titles import MovieContext

ContextLookup = Callable[[str], MovieContext | None]

# Folga para modelos que raciocinam antes da resposta curta: o raciocínio
# conta no limite de saída, e estourá-lo descartaria a resposta.
SPOILER_MAX_TOKENS = 2048


@dataclass(frozen=True)
class SpoilerAnalysis:
    status: SpoilerCheckStatus
    had_synopsis: bool


class SpoilerCheckService:
    def __init__(
        self, chat: ChatClient, context_lookup: ContextLookup, *, timeout: float
    ) -> None:
        self.chat = chat
        self.context_lookup = context_lookup
        self.timeout = timeout

    def analyze(self, movie_id: str, content: str) -> SpoilerAnalysis:
        """Resultado e se a sinopse curta estava disponível (para o log)."""
        if not self.chat.configured:
            return SpoilerAnalysis(SpoilerCheckStatus.UNAVAILABLE, had_synopsis=False)
        context = self.context_lookup(movie_id)
        synopsis = context.synopsis if context else None
        messages = spoiler_check_messages(
            movie_id,
            content,
            title=context.label if context else None,
            synopsis=synopsis,
        )
        try:
            answer = self.chat.complete(
                messages, max_tokens=SPOILER_MAX_TOKENS, timeout=self.timeout
            )
        except AIUnavailableError:
            return SpoilerAnalysis(
                SpoilerCheckStatus.UNAVAILABLE, had_synopsis=synopsis is not None
            )
        return SpoilerAnalysis(
            parse_spoiler_answer(answer), had_synopsis=synopsis is not None
        )

    def check(self, movie_id: str, content: str) -> SpoilerCheckStatus:
        return self.analyze(movie_id, content).status
