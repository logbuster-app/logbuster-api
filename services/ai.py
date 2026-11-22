"""Cliente mínimo de chat para provedores compatíveis com `/chat/completions`.

Gemini, OpenAI, Groq e Anthropic expõem esse formato, então a troca de
provedor é só configuração (`AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`). Toda
falha vira `AIUnavailableError`: quem chama decide o estado `unavailable`
e nunca derruba a requisição (SPEC-BACK-09, RN-02 e RN-03).
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger("uvicorn.error")

Message = dict[str, str]

# Alguns modelos de raciocínio devolvem o "pensamento" antes da resposta.
_THINKING = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


class AIUnavailableError(Exception):
    """IA não configurada, lenta, com erro ou com resposta inutilizável."""


class ChatClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        reasoning_effort: str = "",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        # Ex.: "low" no Gemini, cujos modelos 3 sempre raciocinam. Vazio não envia.
        self.reasoning_effort = reasoning_effort
        self.transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def complete(
        self,
        messages: list[Message],
        *,
        max_tokens: int,
        timeout: float,
        temperature: float = 0.0,
    ) -> str:
        """Texto da primeira escolha, sem espaços nas pontas."""
        if not self.configured:
            raise AIUnavailableError("IA não configurada.")
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        try:
            with httpx.Client(transport=self.transport, timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            if choice.get("finish_reason") == "length":
                raise AIUnavailableError("Resposta truncada pelo limite de tokens.")
            if isinstance(content, str):
                content = _THINKING.sub("", content)
            if not isinstance(content, str) or not content.strip():
                raise AIUnavailableError("Resposta vazia.")
        except AIUnavailableError as exc:
            logger.warning("IA indisponível (%s).", exc)
            raise
        except httpx.HTTPStatusError as exc:
            # Só o status: prompts, textos de usuários e a chave não vão para o log.
            reason = f"HTTP {exc.response.status_code}"
            logger.warning("IA indisponível (%s).", reason)
            raise AIUnavailableError(reason) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("IA indisponível (%s).", type(exc).__name__)
            raise AIUnavailableError(type(exc).__name__) from exc
        return content.strip()
