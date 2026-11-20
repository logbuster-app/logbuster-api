"""Sugestão de spoiler antes de publicar (SPEC-BACK-09, RN-03).

A análise só sugere: não cria, altera nem oculta avaliações, e qualquer
falha da IA responde `unavailable` para o front publicar sem aviso.
"""

from collections.abc import Callable

from domain.enums import SpoilerCheckStatus
from services.ai import AIUnavailableError, ChatClient
from services.ai_prompts import parse_spoiler_answer, spoiler_check_messages

TitleLookup = Callable[[str], str | None]

# Folga para modelos que raciocinam antes da resposta curta: o raciocínio
# conta no limite de saída, e estourá-lo descartaria a resposta.
SPOILER_MAX_TOKENS = 2048


class SpoilerCheckService:
    def __init__(
        self, chat: ChatClient, title_lookup: TitleLookup, *, timeout: float
    ) -> None:
        self.chat = chat
        self.title_lookup = title_lookup
        self.timeout = timeout

    def check(self, movie_id: str, content: str) -> SpoilerCheckStatus:
        if not self.chat.configured:
            return SpoilerCheckStatus.UNAVAILABLE
        messages = spoiler_check_messages(
            movie_id, content, self.title_lookup(movie_id)
        )
        try:
            answer = self.chat.complete(
                messages, max_tokens=SPOILER_MAX_TOKENS, timeout=self.timeout
            )
        except AIUnavailableError:
            return SpoilerCheckStatus.UNAVAILABLE
        return parse_spoiler_answer(answer)
