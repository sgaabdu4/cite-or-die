from cite_or_die.core.extractive_answer import (
    build_extractive_definition_answer,
    has_definition_support,
)
from cite_or_die.core.models import DocumentChunk


def test_extractive_definition_answer_prefers_definition_over_related_process() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="rag-guide.txt",
        ordinal=0,
        text=(
            "Retrieval-augmented generation (RAG) has emerged as an effective "
            "approach for improving factual grounding. Lewis et al. introduced "
            "RAG as a framework that combines model knowledge with external "
            "documents. In many RAG pipelines, a reranker reorders passages."
        ),
    )

    answer = build_extractive_definition_answer("What is RAG?", [chunk])

    assert answer is not None
    assert "framework that combines" in answer.answer
    assert "has emerged" not in answer.answer
    assert "reranker reorders" not in answer.answer
    assert answer.claims[0].citations[0].quote == answer.answer
    assert has_definition_support("What is RAG?", answer)


def test_extractive_definition_answer_returns_none_without_definition_support() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="rag-guide.txt",
        ordinal=0,
        text="In many RAG pipelines, a reranker reorders passages.",
    )

    assert build_extractive_definition_answer("What is RAG?", [chunk]) is None


def test_extractive_definition_answer_ignores_truncated_chunk_boundary() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="rag-guide.txt",
        ordinal=0,
        text=(
            "Retrieval-augmented generation (RAG) has emerged as an effective "
            "approach for improving factual grounding. Introduced RAG as a "
            "framework that combines model knowledge with retrie"
        ),
    )

    answer = build_extractive_definition_answer("What is RAG?", [chunk])

    assert answer is not None
    assert answer.answer.endswith(".")
    assert "retrie" not in answer.answer


def test_extractive_definition_answer_preserves_common_abbreviation_sentence() -> None:
    chunk = DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="rag-guide.txt",
        ordinal=0,
        text=(
            "The introduction discusses generation. Lewis et al. introduced "
            "RAG as a framework that combines model knowledge with external documents."
        ),
    )

    answer = build_extractive_definition_answer("What is RAG?", [chunk])

    assert answer is not None
    assert answer.answer.startswith("Lewis et al. introduced RAG")
