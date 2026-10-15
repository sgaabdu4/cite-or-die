import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuthContext, DocumentChunk, RetrievalHit, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.retrieval.service import RetrievalService


@pytest.mark.asyncio()
async def test_hybrid_retrieval_applies_rerank_signal(settings) -> None:
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id="retrieval", subject="runner", roles=[Role.admin])
    await service.upload(
        ctx,
        "distractor.txt",
        "text/plain",
        b"customer concentration customer concentration customer concentration",
    )
    await service.upload(
        ctx,
        "answer.txt",
        "text/plain",
        b"Customer concentration risk was disclosed because one customer represented revenue.",
    )
    hits = await service.retrieval.retrieve(
        "retrieval", "customer concentration risk revenue", top_k=2
    )

    assert hits[0].chunk.filename == "answer.txt"
    assert hits[0].rerank_score > 0


def test_rerank_candidates_preserve_sparse_matches_for_rerank(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
        rerank_input_k=4,
    )
    retrieval = RetrievalService(settings)
    sparse_match = _hit("sparse", "HR records show regretted attrition of 18 percent.", 0.1)
    fused = {
        **{
            f"graph-{index}": _hit(
                f"graph-{index}",
                f"Contract cross-reference section {index}.",
                10.0 - index,
            )
            for index in range(6)
        },
        sparse_match.chunk.chunk_id: sparse_match,
    }
    sparse = [(sparse_match.chunk, 9.0)]

    candidates = retrieval._rerank_candidates(fused, sparse, top_k=4)

    assert candidates[0].chunk.chunk_id == "sparse"
    assert {hit.chunk.chunk_id for hit in candidates} == {
        "sparse",
        "graph-0",
        "graph-1",
        "graph-2",
    }


def _hit(chunk_id: str, text: str, score: float) -> RetrievalHit:
    return RetrievalHit(
        chunk=DocumentChunk(
            chunk_id=chunk_id,
            tenant_id="tenant-a",
            matter_id="matter-a",
            doc_id=chunk_id,
            filename=f"{chunk_id}.txt",
            text=text,
            ordinal=0,
        ),
        score=score,
    )
