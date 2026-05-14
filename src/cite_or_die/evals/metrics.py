from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import cast

from pydantic import BaseModel

from cite_or_die.core.models import ChatResponse, GuardrailStatus
from cite_or_die.retrieval.embeddings import tokenize
from cite_or_die.retrieval.rerank import canonical_token_set


class EvalMetrics(BaseModel):
    recall_at_8: float
    faithfulness: float
    citation_valid: float
    hybrid_lift_over_bm25: float


def compute_metric_summary(
    records: Sequence[dict[str, object]],
    responses: Sequence[ChatResponse],
    accepted_status: GuardrailStatus,
    bm25_recall_at_8: float,
    retrieved_filenames: Sequence[set[str]] | None = None,
) -> EvalMetrics:
    # Source: https://docs.ragas.io/en/stable/getstarted/evals/
    # RAGAS evaluates saved artifacts with metric gates.
    if len(records) != len(responses):
        raise ValueError("records and responses must have the same length")
    if retrieved_filenames is not None and len(records) != len(retrieved_filenames):
        raise ValueError("records and retrieved_filenames must have the same length")
    if not records:
        raise ValueError("at least one eval record is required")

    recall_hits = 0
    faithful = 0
    citation_valid = 0
    for index, (record, response) in enumerate(zip(records, responses, strict=True)):
        if _recall_hit(record, response, retrieved_filenames, index):
            recall_hits += 1
        if response.guardrails and response.guardrails[-1].status == accepted_status:
            faithful += 1
        if response.citations:
            citation_valid += 1

    recall_at_8 = recall_hits / len(records)
    return EvalMetrics(
        recall_at_8=recall_at_8,
        faithfulness=faithful / len(records),
        citation_valid=citation_valid / len(records),
        hybrid_lift_over_bm25=_relative_lift(recall_at_8, bm25_recall_at_8),
    )


def _recall_hit(
    record: dict[str, object],
    response: ChatResponse,
    retrieved_filenames: Sequence[set[str]] | None,
    index: int,
) -> bool:
    if retrieved_filenames is not None:
        retrieval_id = str(record.get("retrieval_id") or record.get("id") or record.get("doc_id"))
        return f"{retrieval_id}.txt" in retrieved_filenames[index]
    answer_terms_raw = cast(list[object], record.get("answer_terms", []))
    answer_terms = [str(term) for term in answer_terms_raw]
    return _contains_terms(response.answer, answer_terms)


def _relative_lift(value: float, baseline: float) -> float:
    if baseline <= 0:
        return 1.0 if value > 0 else 0.0
    return max(0.0, (value - baseline) / baseline)


def _contains_terms(answer: str, answer_terms: Iterable[str]) -> bool:
    answer_tokens = canonical_token_set(tokenize(answer))
    for term in answer_terms:
        term_tokens = canonical_token_set(tokenize(term))
        if not term_tokens.issubset(answer_tokens):
            return False
    return True
