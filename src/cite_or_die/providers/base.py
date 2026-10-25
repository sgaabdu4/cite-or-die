from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel

from cite_or_die.core.models import DocumentChunk, LLMAnswer


class ProviderResponse(BaseModel):
    answer: LLMAnswer
    model_provider: str
    model_version: str


class Provider(ABC):
    name: str

    @abstractmethod
    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        raise NotImplementedError


class ApiKeyProvider(Provider):
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.api_key = api_key
        self.transport = transport

    async def _post_json(
        self, url: str, headers: dict[str, str], body: dict[str, object]
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
            response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response
