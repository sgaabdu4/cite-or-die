import json

import httpx

from cite_or_die.core.models import DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse


class OpenAIProvider(Provider):
    name = "openai"

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
        async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
            # Source: https://developers.openai.com/api/docs/guides/deployment-checklist
            # OpenAI recommends starting new deployments with the Responses API.
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model_version,
                    "input": prompt,
                    "text": {"format": {"type": "json_object"}},
                },
            )
        response.raise_for_status()
        content = _response_text(response.json())
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


def _response_text(payload: dict[str, object]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output", [])
    if not isinstance(output, list):
        raise ValueError("OpenAI response output was not a list")
    for item in output:
        if not isinstance(item, dict):
            continue
        contents = item.get("content", [])
        if not isinstance(contents, list):
            continue
        for content in contents:
            if isinstance(content, dict):
                text = content.get("text")
                if isinstance(text, str):
                    return text
    raise ValueError("OpenAI response did not include output text")
