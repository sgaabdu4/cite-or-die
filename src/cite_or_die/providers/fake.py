import re

from cite_or_die.core.models import Citation, Claim, DocumentChunk, LLMAnswer
from cite_or_die.providers.base import Provider, ProviderResponse

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_TOKEN = re.compile(r"[A-Za-z0-9]+")


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
        quote = supporting_quote(question, chunk.text)
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


def supporting_quote(question: str, text: str) -> str:
    sentences = [
        sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(text) if sentence.strip()
    ]
    if not sentences:
        return text.strip()
    question_terms = set(_TOKEN.findall(question.lower()))
    if not question_terms:
        return sentences[0]
    return max(
        sentences,
        key=lambda sentence: (
            len(set(_TOKEN.findall(sentence.lower())) & question_terms),
            -len(sentence),
        ),
    )
