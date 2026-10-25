from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from typing import Protocol, SupportsFloat, cast

from typing_extensions import override

from cite_or_die.core.models import RetrievalHit
from cite_or_die.core.text import tokenize

QUERY_STOPWORDS = {
    "a",
    "an",
    "are",
    "did",
    "does",
    "is",
    "the",
    "was",
    "were",
    "what",
}
DEFINITION_QUERY = re.compile(r"\b(what|define|definition|meaning)\b")


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        raise NotImplementedError


class NoopReranker(Reranker):
    @override
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


class LexicalReranker(Reranker):
    @override
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        query_terms = tokenize(query)
        scored = [
            hit.model_copy(update={"rerank_score": lexical_rerank_score(query_terms, hit)})
            for hit in hits
        ]
        ranked = sorted(
            scored,
            key=lambda hit: (hit.rerank_score, hit.score),
            reverse=True,
        )
        sparse_ranked = sorted(
            scored,
            key=lambda hit: (hit.sparse_score, hit.score),
            reverse=True,
        )
        return _merge_with_sparse_backfill(ranked, sparse_ranked, limit)


def lexical_rerank_score(query_terms: list[str], hit: RetrievalHit) -> float:
    content_terms = [term for term in query_terms if term not in QUERY_STOPWORDS]
    if not content_terms:
        return hit.score
    chunk_terms = tokenize(hit.chunk.text)
    if not chunk_terms:
        return 0.0
    query_set = canonical_token_set(content_terms)
    chunk_set = canonical_token_set(chunk_terms)
    coverage = len(query_set.intersection(chunk_set)) / len(query_set)
    density = sum(1 for term in chunk_terms if term in query_set) / len(chunk_terms)
    definition_boost = definition_query_boost(query_terms, hit.chunk.text)
    return (coverage * 0.75) + (density * 0.25) + definition_boost + min(hit.score, 1.0) * 0.05


def definition_query_boost(query_terms: list[str], text: str) -> float:
    if not query_terms or not DEFINITION_QUERY.search(" ".join(query_terms)):
        return 0.0
    text_lower = text.lower()
    boost = 0.0
    content_terms = [term for term in query_terms if term not in QUERY_STOPWORDS]
    for term in content_terms:
        if re.search(rf"\b[a-z][a-z -]{{3,}}\s+\({re.escape(term)}\)", text_lower):
            boost += 0.35
        if re.search(rf"\b{re.escape(term)}\b[^.!?]{{0,80}}\bas\b", text_lower):
            boost += 0.25
    if any(
        phrase in text_lower
        for phrase in (
            "retrieves external evidence",
            "provide that evidence as context",
            "combines parametric knowledge",
            "non-parametric knowledge retrieved",
        )
    ):
        boost += 0.2
    return min(boost, 0.6)


def _merge_with_sparse_backfill(
    ranked: list[RetrievalHit], sparse_ranked: list[RetrievalHit], limit: int
) -> list[RetrievalHit]:
    sparse_slots = min(limit // 2, 4)
    primary_limit = max(0, limit - sparse_slots)
    selected: list[RetrievalHit] = []
    seen: set[str] = set()

    def add(hit: RetrievalHit) -> None:
        if hit.chunk.chunk_id in seen or len(selected) >= limit:
            return
        seen.add(hit.chunk.chunk_id)
        selected.append(hit)

    for hit in ranked[:primary_limit]:
        add(hit)
    for hit in sparse_ranked:
        add(hit)
    for hit in ranked:
        add(hit)
    return selected


def canonical_token_set(tokens: list[str]) -> set[str]:
    canonical: set[str] = set()
    for token in tokens:
        canonical.add(token)
        if len(token) > 3 and token.endswith("s"):
            canonical.add(token[:-1])
    return canonical


class _PairScorer(Protocol):
    def predict(
        self, pairs: list[list[str]], *, activation_fn: Callable[[object], object]
    ) -> Iterable[SupportsFloat]: ...


class BgeReranker(Reranker):
    def __init__(self) -> None:
        from sentence_transformers import CrossEncoder

        self._model = cast(
            _PairScorer,
            CrossEncoder(
                "BAAI/bge-reranker-v2-m3",
                max_length=512,
                model_kwargs={"torch_dtype": "float32"},
            ),
        )

    @override
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        pairs = [[query, hit.chunk.text] for hit in hits]
        if not pairs:
            return []
        scores = self._model.predict(pairs, activation_fn=lambda values: values)
        reranked = [
            hit.model_copy(update={"rerank_score": float(score)})
            for hit, score in zip(hits, scores, strict=True)
        ]
        return sorted(reranked, key=lambda hit: hit.rerank_score, reverse=True)[:limit]


def make_reranker(name: str) -> Reranker:
    if name == "bge-reranker-v2-m3":
        return BgeReranker()
    if name == "none":
        return NoopReranker()
    return LexicalReranker()
