import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.retrieval.service import RetrievalService


@pytest.mark.asyncio()
async def test_citation_graph_adds_at_least_15_percent_recall_lift(tmp_path) -> None:
    query = "What requirement applies to Project Redwood?"
    expected = {"target"}

    baseline = await _recall_at_8(tmp_path / "baseline", query, expected, graph_enabled=False)
    graph = await _recall_at_8(tmp_path / "graph", query, expected, graph_enabled=True)

    assert baseline == 0.0
    assert graph - baseline >= 0.15


async def _recall_at_8(
    data_dir,
    query: str,
    expected_chunk_ids: set[str],
    *,
    graph_enabled: bool,
) -> float:
    settings = Settings(
        app_env="test",
        data_dir=data_dir,
        auth_secret="test-secret-with-at-least-32-bytes",
        citation_graph_enabled=graph_enabled,
        retrieval_candidate_k=8,
        rerank_input_k=8,
        reranker_provider="none",
    )
    retrieval = RetrievalService(settings)
    await retrieval.index_chunks("tenant-a", _multi_hop_chunks(), "matter-a")

    hits = await retrieval.retrieve("tenant-a", query, 8, "matter-a")
    retrieved_ids = {hit.chunk.chunk_id for hit in hits}
    return len(expected_chunk_ids.intersection(retrieved_ids)) / len(expected_chunk_ids)


def _multi_hop_chunks() -> list[DocumentChunk]:
    chunks = [
        DocumentChunk(
            chunk_id="source",
            tenant_id="tenant-a",
            matter_id="matter-a",
            doc_id="deal",
            filename="deal.md",
            text="Project Redwood is governed by Section 9.",
            ordinal=0,
        ),
        DocumentChunk(
            chunk_id="target",
            tenant_id="tenant-a",
            matter_id="matter-a",
            doc_id="deal",
            filename="deal.md",
            text="Section 9 requires board consent before closing.",
            ordinal=1,
        ),
    ]
    for index in range(12):
        chunks.append(
            DocumentChunk(
                chunk_id=f"distractor-{index}",
                tenant_id="tenant-a",
                matter_id="matter-a",
                doc_id=f"distractor-{index}",
                filename="distractor.md",
                text=f"Generic requirement applies to routine approval planning memo {index}.",
                ordinal=0,
            )
        )
    return chunks
