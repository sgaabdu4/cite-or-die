from abc import ABC, abstractmethod

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
