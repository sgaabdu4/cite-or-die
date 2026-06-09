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


def test_verifier_removes_unsupported_claim_text_from_answer() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="source.txt",
        ordinal=0,
        text="Automotive leasing revenue includes direct operating lease amortization.",
    )
    answer = LLMAnswer(
        answer=(
            "Automotive leasing revenue includes direct operating lease amortization. "
            "Unsupported revenue detail."
        ),
        claims=[
            Claim(
                text="Automotive leasing revenue includes direct operating lease amortization.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page=None,
                        quote=(
                            "Automotive leasing revenue includes direct operating "
                            "lease amortization."
                        ),
                    )
                ],
            ),
            Claim(
                text="Unsupported revenue detail.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page=None,
                        quote="not in the document",
                    )
                ],
            ),
        ],
    )

    verified, decision = CitationVerifier().verify(answer, [chunk])

    assert decision.status == GuardrailStatus.repaired
    assert verified.answer == (
        "Automotive leasing revenue includes direct operating lease amortization."
    )
    assert "Unsupported revenue detail" not in verified.answer
    assert [claim.text for claim in verified.claims] == [
        "Automotive leasing revenue includes direct operating lease amortization."
    ]


def test_verifier_rejects_wrong_type_object_for_question() -> None:
    litter_chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="cat-guide.pdf",
        ordinal=0,
        page=17,
        text="A covered litter box may help contain tracked litter.",
    )
    personality_chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="cat-guide.pdf",
        ordinal=1,
        page=11,
        text="Every cat has a different personality.",
    )
    answer = LLMAnswer(
        answer=(
            "The text mentions different types of litter boxes and various "
            "personality types."
        ),
        claims=[
            Claim(
                text=(
                    "The text mentions different types of litter boxes and various "
                    "personality types."
                ),
                citations=[
                    Citation(
                        chunk_id=litter_chunk.chunk_id,
                        doc_id=litter_chunk.doc_id,
                        filename=litter_chunk.filename,
                        page=litter_chunk.page,
                        quote="covered litter box",
                    ),
                    Citation(
                        chunk_id=personality_chunk.chunk_id,
                        doc_id=personality_chunk.doc_id,
                        filename=personality_chunk.filename,
                        page=personality_chunk.page,
                        quote="Every cat has a different personality.",
                    ),
                ],
            )
        ],
    )

    verified, decision = CitationVerifier().verify(
        answer,
        [litter_chunk, personality_chunk],
        question="What are the different types of cats?",
    )

    assert decision.status == GuardrailStatus.rejected
    assert decision.metadata["dropped_claims"] == 1
    assert verified.claims == []
    assert "litter boxes" not in verified.answer


def test_verifier_accepts_matching_type_object_for_question() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="cat-guide.pdf",
        ordinal=0,
        text="The guide lists indoor cats and outdoor cats as types of cats.",
    )
    answer = LLMAnswer(
        answer="The guide lists indoor cats and outdoor cats as types of cats.",
        claims=[
            Claim(
                text="The guide lists indoor cats and outdoor cats as types of cats.",
                citations=[
                    Citation(
                        chunk_id=chunk.chunk_id,
                        doc_id=chunk.doc_id,
                        filename=chunk.filename,
                        page=None,
                        quote="indoor cats and outdoor cats as types of cats",
                    )
                ],
            )
        ],
    )

    verified, decision = CitationVerifier().verify(
        answer, [chunk], question="What are the different types of cats?"
    )

    assert decision.status == GuardrailStatus.accepted
    assert verified.claims
