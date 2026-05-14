import pytest

from cite_or_die.core.models import DocumentChunk, RetrievalHit
from cite_or_die.retrieval.rerank import LexicalReranker


@pytest.mark.asyncio()
async def test_lexical_reranker_promotes_precise_query_coverage() -> None:
    stuffed = DocumentChunk(
        tenant_id="t1",
        doc_id="stuffed",
        filename="stuffed.txt",
        ordinal=0,
        text="customer concentration customer concentration customer concentration",
    )
    precise = DocumentChunk(
        tenant_id="t1",
        doc_id="precise",
        filename="precise.txt",
        ordinal=0,
        text="Customer concentration risk was disclosed because one customer represented revenue.",
    )

    hits = [
        RetrievalHit(chunk=stuffed, score=1.0),
        RetrievalHit(chunk=precise, score=0.8),
    ]

    reranked = await LexicalReranker().rerank(
        "customer concentration risk revenue", hits, limit=2
    )

    assert reranked[0].chunk.doc_id == "precise"
    assert reranked[0].rerank_score > reranked[1].rerank_score


@pytest.mark.asyncio()
async def test_lexical_reranker_keeps_sparse_high_confidence_hits() -> None:
    hits = [
        RetrievalHit(
            chunk=DocumentChunk(
                tenant_id="t1",
                doc_id=f"lexical-{index}",
                filename=f"lexical-{index}.txt",
                ordinal=0,
                text="customer concentration risk revenue",
            ),
            score=0.2,
            sparse_score=1.0,
        )
        for index in range(4)
    ]
    sparse_hit = RetrievalHit(
        chunk=DocumentChunk(
            tenant_id="t1",
            doc_id="sparse",
            filename="sparse.txt",
            ordinal=0,
            text="revenue",
        ),
        score=0.1,
        sparse_score=100.0,
    )

    reranked = await LexicalReranker().rerank(
        "customer concentration risk revenue", [*hits, sparse_hit], limit=4
    )

    assert any(hit.chunk.doc_id == "sparse" for hit in reranked)
