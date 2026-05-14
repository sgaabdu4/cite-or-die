from cite_or_die.core.models import Citation, Claim, DocumentChunk, GuardrailStatus, LLMAnswer
from cite_or_die.security.citation_verifier import CitationVerifier


def test_verifier_accepts_verbatim_quote() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="source.txt",
        ordinal=0,
        text="The acquisition closed on 14 May with a cash consideration of 10 million.",
    )
    answer = LLMAnswer(
        answer="The acquisition closed on 14 May.",
        claims=[
            Claim(
                text="The acquisition closed on 14 May.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page=None,
                        quote="acquisition closed on 14 May",
                    )
                ],
            )
        ],
    )

    verified, decision = CitationVerifier().verify(answer, [chunk])

    assert decision.status == GuardrailStatus.accepted
    assert verified.claims


def test_verifier_rejects_unsupported_quote() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="source.txt",
        ordinal=0,
        text="Only verified source text is allowed.",
    )
    answer = LLMAnswer(
        answer="Unsupported claim.",
        claims=[
            Claim(
                text="Unsupported claim.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page=None,
                        quote="not in the document",
                    )
                ],
            )
        ],
    )

    verified, decision = CitationVerifier().verify(answer, [chunk])

    assert decision.status == GuardrailStatus.rejected
    assert verified.claims == []
    assert verified.refusal is not None
