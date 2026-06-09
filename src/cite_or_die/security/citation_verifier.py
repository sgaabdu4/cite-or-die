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
WORD = re.compile(r"[a-z0-9]+")
TYPE_QUERY = re.compile(
    r"\b(?:types?|kinds?|categories)\s+of\s+"
    r"(?P<object>[a-z][a-z -]{1,80}?)(?=[()?,.;:]|\band\b|$)"
)
ADJECTIVE_TYPE = re.compile(
    r"\b(?P<object>[a-z][a-z -]{2,40})\s+(?:types?|kinds?|categories)\b"
)
QUESTION_STOPWORDS = {
    "are",
    "different",
    "does",
    "from",
    "kind",
    "kinds",
    "list",
    "listed",
    "mention",
    "mentioned",
    "of",
    "source",
    "the",
    "there",
    "type",
    "types",
    "various",
    "what",
}


def normalize_for_match(text: str) -> str:
    return SPACE.sub(" ", unicodedata.normalize("NFKC", text)).strip().casefold()


def answer_from_claims(claims: Iterable[Claim]) -> str:
    parts: list[str] = []
    for claim in claims:
        text = claim.text.strip()
        if text:
            parts.append(text)
        else:
            parts.extend(
                citation.quote.strip()
                for citation in claim.citations
                if citation.quote.strip()
            )
    return " ".join(parts)


def _canonical_word(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return f"{word[:-3]}y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _topic_terms(text: str) -> set[str]:
    return {
        _canonical_word(word)
        for word in WORD.findall(normalize_for_match(text))
        if len(word) > 2 and word not in QUESTION_STOPWORDS
    }


def _type_query_target_terms(question: str | None) -> set[str]:
    if not question:
        return set()
    normalized = normalize_for_match(question)
    targets: set[str] = set()
    for match in TYPE_QUERY.finditer(normalized):
        targets.update(_topic_terms(match.group("object")))
    return targets


def _answers_type_query(
    question: str | None, claim: Claim, citations: list[Citation]
) -> bool:
    target_terms = _type_query_target_terms(question)
    if not target_terms:
        return True

    claim_text = normalize_for_match(claim.text)
    cited_text = " ".join(citation.quote for citation in citations)
    combined_terms = _topic_terms(f"{claim_text} {cited_text}")
    if not target_terms.intersection(combined_terms):
        return False

    for pattern in (TYPE_QUERY, ADJECTIVE_TYPE):
        for match in pattern.finditer(claim_text):
            object_terms = _topic_terms(match.group("object"))
            if object_terms and not object_terms.intersection(target_terms):
                return False
    return True


class CitationVerifier:
    """Verifies citations by literal normalized substring match against retrieved chunks."""

    def verify(
        self,
        answer: LLMAnswer,
        chunks: Iterable[DocumentChunk],
        question: str | None = None,
    ) -> tuple[LLMAnswer, GuardrailDecision]:
        chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
        repaired_claims: list[Claim] = []
        dropped = 0
        dropped_claims = 0

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
                                "tenant_id": chunk.tenant_id,
                                "matter_id": chunk.matter_id,
                                "page": chunk.page,
                            }
                        )
                    )
                else:
                    dropped += 1
            if verified_citations and _answers_type_query(
                question, claim, verified_citations
            ):
                repaired_claims.append(claim.model_copy(update={"citations": verified_citations}))
            elif verified_citations:
                dropped += len(verified_citations)
                dropped_claims += 1

        if not repaired_claims:
            refusal = (
                "I could not verify the answer against the retrieved source text, "
                "so I am not returning an unsupported claim."
            )
            reason = "no claim had a verbatim citation in retrieved chunks"
            if dropped_claims:
                reason = "no claim directly answered the type requested in the question"
            return (
                LLMAnswer(answer=refusal, claims=[], refusal=refusal),
                GuardrailDecision(
                    name="verbatim_citation_verifier",
                    status=GuardrailStatus.rejected,
                    reason=reason,
                    metadata={
                        "dropped_citations": dropped,
                        "dropped_claims": dropped_claims,
                    },
                ),
            )

        return (
            answer.model_copy(
                update={
                    "answer": answer.answer
                    if dropped == 0
                    else answer_from_claims(repaired_claims),
                    "claims": repaired_claims,
                }
            ),
            GuardrailDecision(
                name="verbatim_citation_verifier",
                status=GuardrailStatus.repaired if dropped else GuardrailStatus.accepted,
                reason="all returned claims have at least one verbatim citation"
                if not dropped
                else "dropped unsupported citations, claims, or off-question claims",
                metadata={
                    "dropped_citations": dropped,
                    "dropped_claims": dropped_claims,
                },
            ),
        )
