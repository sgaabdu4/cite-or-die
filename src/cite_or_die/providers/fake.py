from cite_or_die.core.models import Citation, Claim, DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse


class FakeLLM(Provider):
    name = "fake"

    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        if not chunks:
            answer = LLMAnswer(answer="No sources are available for this tenant.", claims=[])
            return ProviderResponse(
                answer=answer, model_provider=self.name, model_version=model_version
            )

        chunk = chunks[0]
        quote = chunk.text[: min(len(chunk.text), 220)].strip()
        claim_text = f"Based on the retrieved source, {quote}"
        answer = LLMAnswer(
            answer=claim_text,
            claims=[
                Claim(
                    text=claim_text,
                    citations=[
                        Citation(
                            chunk_id=chunk.chunk_id,
                            doc_id=chunk.doc_id,
                            filename=chunk.filename,
                            page=chunk.page,
                            quote=quote,
                        )
                    ],
                )
            ],
        )
        return ProviderResponse(
            answer=answer, model_provider=self.name, model_version=model_version
        )
