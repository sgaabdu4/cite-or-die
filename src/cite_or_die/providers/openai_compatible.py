import json

import httpx

from cite_or_die.core.models import DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse
from cite_or_die.providers.openai import _json_prompt


class OpenAICompatibleProvider(Provider):
    name = "openai-compatible"

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport

    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        prompt = _json_prompt(question, chunks)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json={
                    "model": model_version,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        content = _chat_completion_text(response.json())
        return ProviderResponse(
            answer=LLMAnswer.model_validate(json.loads(content)),
            model_provider=self.name,
            model_version=model_version,
        )


def _chat_completion_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices", [])
    if not isinstance(choices, list):
        raise ValueError("OpenAI-compatible response choices was not a list")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise ValueError("OpenAI-compatible response did not include message content")
