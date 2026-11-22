import json

import httpx
import pytest

from services.ai import AIUnavailableError, ChatClient

MESSAGES = [{"role": "user", "content": "Olá"}]


def completion(content="Resposta", finish_reason="stop"):
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ]
    }


def client_with(handler, **overrides):
    options = {
        "base_url": "https://ia.test/v1/",
        "api_key": "chave-de-teste",
        "model": "modelo-de-teste",
        "transport": httpx.MockTransport(handler),
    }
    return ChatClient(**{**options, **overrides})


def test_sends_openai_compatible_request_and_returns_stripped_text():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion("  Texto da IA \n"))

    answer = client_with(handler).complete(
        MESSAGES, max_tokens=50, timeout=3, temperature=0.3
    )

    assert answer == "Texto da IA"
    assert seen["url"] == "https://ia.test/v1/chat/completions"
    assert seen["auth"] == "Bearer chave-de-teste"
    assert seen["body"] == {
        "model": "modelo-de-teste",
        "messages": MESSAGES,
        "max_tokens": 50,
        "temperature": 0.3,
    }


def test_sends_reasoning_effort_only_when_configured():
    bodies = []

    def handler(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json=completion())

    client_with(handler, reasoning_effort="low").complete(
        MESSAGES, max_tokens=10, timeout=1
    )
    client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1)

    assert bodies[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in bodies[1]


def test_strips_reasoning_block_from_answer():
    def handler(_request):
        return httpx.Response(200, json=completion("<think>\nanálise\n</think>\nSIM"))

    assert client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1) == "SIM"


def test_answer_with_only_reasoning_is_unavailable():
    def handler(_request):
        return httpx.Response(200, json=completion("<think>só isso</think>"))

    with pytest.raises(AIUnavailableError):
        client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1)


@pytest.mark.parametrize("missing", ["base_url", "api_key", "model"])
def test_unconfigured_client_never_calls_the_provider(missing):
    def handler(_request):
        raise AssertionError("Não deveria chamar a IA")

    client = client_with(handler, **{missing: ""})

    assert client.configured is False
    with pytest.raises(AIUnavailableError):
        client.complete(MESSAGES, max_tokens=10, timeout=1)


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, json={"error": "falha"}),
        lambda request: httpx.Response(429, json={"error": "limite"}),
        lambda request: httpx.Response(200, text="não é json"),
        lambda request: httpx.Response(200, json={"choices": []}),
        lambda request: httpx.Response(200, json=completion(content=None)),
        lambda request: httpx.Response(200, json=completion(content="   ")),
        lambda request: httpx.Response(
            200, json=completion("Texto cortado", finish_reason="length")
        ),
    ],
    ids=["500", "429", "json", "sem-escolha", "nulo", "vazio", "truncado"],
)
def test_provider_failures_become_unavailable(handler):
    with pytest.raises(AIUnavailableError):
        client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1)


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError])
def test_timeouts_and_network_errors_become_unavailable(error):
    def handler(request):
        raise error("falha", request=request)

    with pytest.raises(AIUnavailableError):
        client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1)


def test_http_error_log_includes_status(caplog):
    def handler(_request):
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    with pytest.raises(AIUnavailableError, match="HTTP 503"):
        client_with(handler).complete(MESSAGES, max_tokens=10, timeout=1)
    assert "HTTP 503" in caplog.text


def test_failure_log_does_not_leak_prompt(caplog):
    def handler(_request):
        return httpx.Response(500)

    secret = [{"role": "user", "content": "texto-privado-do-usuario"}]
    with pytest.raises(AIUnavailableError):
        client_with(handler).complete(secret, max_tokens=10, timeout=1)

    assert "texto-privado-do-usuario" not in caplog.text
    assert "chave-de-teste" not in caplog.text
