import re
import unicodedata
from collections.abc import Iterable

from cite_or_die.core.models import (
    Citation,
    Claim,
    DocumentChunk,
    GuardrailDecision,
    GuardrailStatus,
    LLMAnswer,
)

SPACE = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    return SPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()


class CitationVerifier:
    """Verifies citations by literal normalized substring match against retrieved chunks."""

    def verify(
        self, answer: LLMAnswer, chunks: Iterable[DocumentChunk]
    ) -> tuple[LLMAnswer, GuardrailDecision]:
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        repaired_claims: list[Claim] = []
        dropped = 0

        for claim in answer.claims:
            verified_citations: list[Citation] = []
            for citation in claim.citations:
                chunk = chunk_by_id.get(citation.chunk_id)
                if chunk is None:
                    dropped += 1
                    continue
                if normalize_for_match(citation.quote) in normalize_for_match(chunk.text):
                    verified_citations.append(
                        citation.model_copy(
                            update={
                                "doc_id": chunk.doc_id,
                                "filename": chunk.filename,
                                "page": chunk.page,
                            }
                        )
                    )
                else:
                    dropped += 1
            if verified_citations:
                repaired_claims.append(claim.model_copy(update={"citations": verified_citations}))

        if not repaired_claims:
            refusal = (
                "I could not verify the answer against the retrieved source text, "
                "so I am not returning an unsupported claim."
            )
            return (
                LLMAnswer(answer=refusal, claims=[], refusal=refusal),
                GuardrailDecision(
                    name="verbatim_citation_verifier",
                    status=GuardrailStatus.rejected,
                    reason="no claim had a verbatim citation in retrieved chunks",
                    metadata={"dropped_citations": dropped},
                ),
            )

        return (
            answer.model_copy(update={"claims": repaired_claims}),
            GuardrailDecision(
                name="verbatim_citation_verifier",
                status=GuardrailStatus.repaired if dropped else GuardrailStatus.accepted,
                reason="all returned claims have at least one verbatim citation"
                if not dropped
                else "dropped unsupported citations or claims",
                metadata={"dropped_citations": dropped},
            ),
        )
