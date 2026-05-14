import json

import httpx
import pytest
from pydantic import SecretStr

from cite_or_die.core.config import Settings
from cite_or_die.core.models import Citation, Claim, DocumentChunk, LLMAnswer
from cite_or_die.providers.anthropic import AnthropicProvider
from cite_or_die.providers.factory import make_provider
from cite_or_die.providers.ollama import OllamaProvider
from cite_or_die.providers.openai import OpenAIProvider
from cite_or_die.providers.openai_compatible import OpenAICompatibleProvider


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        tenant_id="t",
        matter_id="m",
        doc_id="d",
        filename="source.txt",
        text="Provider smoke says cite-or-die sends only retrieved chunks.",
        ordinal=0,
    )


def _answer() -> str:
    chunk = _chunk()
    answer = LLMAnswer(
        answer="Provider smoke says cite-or-die sends only retrieved chunks.",
        claims=[
            Claim(
                text="Provider smoke says cite-or-die sends only retrieved chunks.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        tenant_id=chunk.tenant_id,
                        matter_id=chunk.matter_id,
                        quote=chunk.text,
                    )
                ],
            )
        ],
    )
    return answer.model_dump_json()


@pytest.mark.asyncio()
async def test_openai_provider_uses_responses_api() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"output_text": _answer()})

    provider = OpenAIProvider("test-key", transport=httpx.MockTransport(handler))
    response = await provider.generate("What does provider smoke say?", [_chunk()], "gpt-test")

    assert response.model_provider == "openai"
    assert response.answer.claims
    assert str(requests[0].url) == "https://api.openai.com/v1/responses"
    payload = json.loads(requests[0].content)
    assert payload["text"]["format"]["type"] == "json_object"


@pytest.mark.asyncio()
async def test_openai_compatible_provider_uses_chat_completions() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": _answer()}}]})

    provider = OpenAICompatibleProvider(
        "https://models.example.test/v1",
        "compatible-key",
        transport=httpx.MockTransport(handler),
    )
    response = await provider.generate("What does provider smoke say?", [_chunk()], "model-test")

    assert response.model_provider == "openai-compatible"
    assert response.answer.claims
    assert str(requests[0].url) == "https://models.example.test/v1/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer compatible-key"
    payload = json.loads(requests[0].content)
    assert payload["response_format"]["type"] == "json_object"


@pytest.mark.asyncio()
async def test_anthropic_provider_parses_message_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        return httpx.Response(200, json={"content": [{"type": "text", "text": _answer()}]})

    provider = AnthropicProvider("test-key", transport=httpx.MockTransport(handler))
    response = await provider.generate("What does provider smoke say?", [_chunk()], "claude-test")

    assert response.model_provider == "anthropic"
    assert response.answer.claims


@pytest.mark.asyncio()
async def test_ollama_provider_parses_generate_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://ollama.local/api/generate"
        return httpx.Response(200, json={"response": _answer()})

    provider = OllamaProvider("http://ollama.local", transport=httpx.MockTransport(handler))
    response = await provider.generate("What does provider smoke say?", [_chunk()], "local-test")

    assert response.model_provider == "ollama"
    assert response.answer.claims


def test_provider_factory_selects_all_configured_providers() -> None:
    assert make_provider(Settings(llm_provider="fake")).name == "fake"
    assert (
        make_provider(
            Settings(llm_provider="anthropic", anthropic_api_key=SecretStr("anthropic-key"))
        ).name
        == "anthropic"
    )
    assert (
        make_provider(Settings(llm_provider="openai", openai_api_key=SecretStr("openai-key"))).name
        == "openai"
    )
    assert (
        make_provider(
            Settings(
                llm_provider="openai-compatible",
                openai_compatible_api_key=SecretStr("compatible-key"),
                openai_compatible_base_url="https://models.example.test/v1",
            )
        ).name
        == "openai-compatible"
    )
    assert make_provider(Settings(llm_provider="ollama")).name == "ollama"
