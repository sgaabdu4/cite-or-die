import json
from pathlib import Path

import pytest

from cite_or_die.core.models import AuthContext, ChatRequest, GuardrailStatus, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.evals.metrics import EvalMetrics, compute_metric_summary


def load_t2_subset() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in Path("examples/t2ragbench_subset.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


@pytest.mark.asyncio()
async def test_t2ragbench_subset_gate(settings) -> None:
    records = load_t2_subset()
    service = CiteOrDieService(settings)
    ctx = AuthContext(tenant_id="t2", subject="eval-runner", roles=[Role.admin])
    for record in records:
        await service.upload(
            ctx,
            f"{record['id']}.txt",
            "text/plain",
            record["context"].encode("utf-8"),
        )

    responses = []
    retrieved_filenames = []
    bm25_hits = 0
    for record in records:
        expected_filename = f"{record['id']}.txt"
        question = str(record["question"])
        hits = await service.retrieval.retrieve("t2", question, top_k=8)
        retrieved_filenames.append({hit.chunk.filename for hit in hits})
        bm25_hits += any(
            chunk.filename == expected_filename
            for chunk, _score in service.retrieval.bm25.search("t2", question, limit=8)
        )
        responses.append(await service.chat(ctx, ChatRequest(question=question, top_k=8)))

    bm25_recall_at_8 = bm25_hits / len(records)
    metrics = compute_metric_summary(
        records,
        responses,
        accepted_status=GuardrailStatus.accepted,
        bm25_recall_at_8=bm25_recall_at_8,
        retrieved_filenames=retrieved_filenames,
    )

    assert isinstance(metrics, EvalMetrics)
    assert metrics.recall_at_8 >= 0.80
    assert metrics.faithfulness >= 0.85
    assert metrics.citation_valid >= 0.95
    assert metrics.hybrid_lift_over_bm25 >= 0.0
