import json

import httpx

from cite_or_die.core.models import DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse
from cite_or_die.providers.network import safe_async_transport_for_url
from cite_or_die.providers.openai import _json_prompt


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = api_key
        self.transport = transport

    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        prompt = _json_prompt(question, chunks)
        transport = self.transport or safe_async_transport_for_url(
            "https://api.anthropic.com/v1/messages"
        )
        async with httpx.AsyncClient(timeout=60, transport=transport) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model_version,
                    "max_tokens": 1200,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        response.raise_for_status()
        text = response.json()["content"][0]["text"]
        return ProviderResponse(
            answer=LLMAnswer.model_validate(json.loads(text)),
            model_provider=self.name,
            model_version=model_version,
        )
