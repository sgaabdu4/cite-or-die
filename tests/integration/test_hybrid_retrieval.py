import pytest

from cite_or_die.core.models import AuthContext, Role
from cite_or_die.core.service import CiteOrDieService


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
