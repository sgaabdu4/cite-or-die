import sys
from collections.abc import Callable
from types import ModuleType

import pytest

from cite_or_die.core.models import DocumentChunk, RetrievalHit
from cite_or_die.retrieval.rerank import BgeReranker, LexicalReranker


@pytest.mark.asyncio()
@pytest.mark.parametrize("scores", [[], [-5.5], [-5.5, 4.25, 1.0]])
async def test_bge_reranker_preserves_raw_scores_without_flagembedding(
    monkeypatch: pytest.MonkeyPatch, scores: list[float]
) -> None:
    calls: list[list[list[str]]] = []

    class CrossEncoder:
        def __init__(self, model: str, *, max_length: int, model_kwargs: dict[str, str]) -> None:
            assert model == "BAAI/bge-reranker-v2-m3"
            assert max_length == 512
            assert model_kwargs == {"torch_dtype": "float32"}

        def predict(
            self,
            pairs: list[list[str]],
            *,
            activation_fn: Callable[[list[float]], list[float]],
        ) -> list[float]:
            calls.append(pairs)
            return activation_fn(scores)

    module = ModuleType("sentence_transformers")
    monkeypatch.setattr(module, "CrossEncoder", CrossEncoder, raising=False)
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    monkeypatch.setitem(sys.modules, "FlagEmbedding", None)
    hits = [
        RetrievalHit(
            chunk=DocumentChunk(
                tenant_id="t1",
                doc_id=str(index),
                filename="document.txt",
                ordinal=index,
                text=f"Passage {index}",
            ),
            score=1.0,
        )
        for index in range(len(scores))
    ]
    ranked = await BgeReranker().rerank("query", hits, limit=2)
    assert [hit.rerank_score for hit in ranked] == sorted(scores, reverse=True)[:2]
    assert calls == ([[["query", hit.chunk.text] for hit in hits]] if hits else [])
    assert all(hit.rerank_score == 0.0 for hit in hits)


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

    reranked = await LexicalReranker().rerank("customer concentration risk revenue", hits, limit=2)

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


@pytest.mark.asyncio()
async def test_lexical_reranker_promotes_definition_for_what_is_query() -> None:
    mention = DocumentChunk(
        tenant_id="t1",
        doc_id="mention",
        filename="mention.txt",
        ordinal=0,
        text="An evaluation framework for RAG pipelines measures retrieval quality.",
    )
    definition = DocumentChunk(
        tenant_id="t1",
        doc_id="definition",
        filename="definition.txt",
        ordinal=0,
        text=(
            "Retrieval-augmented generation (RAG) retrieves external evidence and "
            "provides that evidence as context during answer generation."
        ),
    )

    reranked = await LexicalReranker().rerank(
        "what is RAG?",
        [
            RetrievalHit(chunk=mention, score=0.9, sparse_score=1.0),
            RetrievalHit(chunk=definition, score=0.4, sparse_score=0.4),
        ],
        limit=2,
    )

    assert reranked[0].chunk.doc_id == "definition"
