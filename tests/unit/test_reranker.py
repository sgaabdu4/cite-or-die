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
