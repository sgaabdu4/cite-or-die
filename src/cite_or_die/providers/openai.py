import json

import httpx

from cite_or_die.core.models import DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse


class OpenAIProvider(Provider):
    name = "openai"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        prompt = _json_prompt(question, chunks)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model_version,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return ProviderResponse(
            answer=LLMAnswer.model_validate(json.loads(content)),
            model_provider=self.name,
            model_version=model_version,
        )


def _json_prompt(question: str, chunks: list[DocumentChunk]) -> str:
    source_pack = [
        {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "filename": chunk.filename,
            "page": chunk.page,
            "text": chunk.text,
        }
        for chunk in chunks
    ]
    return (
        "Answer only from the provided chunks. Return JSON matching "
        "{'answer': str, 'claims': [{'text': str, 'citations': "
        "[{'chunk_id': str, 'doc_id': str, 'filename': str, 'page': int|null, 'quote': str}]}]}. "
        "Every quote must be copied verbatim from a chunk.\n\n"
        f"Question: {question}\nChunks: {json.dumps(source_pack)}"
    )
