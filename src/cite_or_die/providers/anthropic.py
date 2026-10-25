import json

from typing_extensions import override

from cite_or_die.core.models import DocumentChunk, LLMAnswer
from cite_or_die.providers.base import ApiKeyProvider, ProviderResponse
from cite_or_die.providers.openai import _json_prompt


class AnthropicProvider(ApiKeyProvider):
    name = "anthropic"

    @override
    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        response = await self._post_json(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            body={
                "model": model_version,
                "max_tokens": 1200,
                "temperature": 0,
                "messages": [{"role": "user", "content": _json_prompt(question, chunks)}],
            },
        )
        text = response.json()["content"][0]["text"]
        return ProviderResponse(
            answer=LLMAnswer.model_validate(json.loads(text)),
            model_provider=self.name,
            model_version=model_version,
        )
