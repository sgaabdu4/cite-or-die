import asyncio
from pathlib import Path

from pytest_benchmark.fixture import BenchmarkFixture

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.retrieval.service import RetrievalService


def test_hybrid_retrieval_with_thirty_rerank_candidates(
    benchmark: BenchmarkFixture, tmp_path: Path
) -> None:
    service = RetrievalService(
        Settings(
            app_env="test",
            data_dir=tmp_path,
            rerank_input_k=30,
            vector_backend="memory",
            embedding_provider="hash",
            reranker_provider="lexical",
        )
    )
    chunks = [
        DocumentChunk(
            chunk_id=f"chunk-{index}",
            tenant_id="performance",
            doc_id=f"document-{index}",
            filename=f"filing-{index}.txt",
            text=f"Project Redwood contract {index} requires board consent before closing.",
            ordinal=index,
        )
        for index in range(100)
    ]
    with asyncio.Runner() as runner:
        runner.run(service.index_chunks("performance", chunks))

        def retrieve() -> None:
            hits = runner.run(
                service.retrieve("performance", "What does Project Redwood require?", 8)
            )
            assert len(hits) == 8
            assert all("board consent" in hit.chunk.text for hit in hits)

        benchmark.pedantic(retrieve, rounds=100, iterations=1, warmup_rounds=10)
