from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
from typing import Any, cast

from cite_or_die.core.models import RetrievalHit
from cite_or_die.retrieval.embeddings import tokenize

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


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        raise NotImplementedError


class NoopReranker(Reranker):
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        return sorted(hits, key=lambda hit: hit.score, reverse=True)[:limit]


class LexicalReranker(Reranker):
    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        query_terms = [term for term in tokenize(query) if term not in QUERY_STOPWORDS]
        scored = [
            hit.model_copy(update={"rerank_score": lexical_rerank_score(query_terms, hit)})
            for hit in hits
        ]
        return sorted(
            scored,
            key=lambda hit: (hit.rerank_score, hit.score),
            reverse=True,
        )[:limit]


def lexical_rerank_score(query_terms: list[str], hit: RetrievalHit) -> float:
    # Source: https://arxiv.org/pdf/2605.12028 supports hybrid retrieval followed by reranking.
    if not query_terms:
        return hit.score
    chunk_terms = tokenize(hit.chunk.text)
    if not chunk_terms:
        return 0.0
    query_set = canonical_token_set(query_terms)
    chunk_set = canonical_token_set(chunk_terms)
    coverage = len(query_set.intersection(chunk_set)) / len(query_set)
    density = sum(1 for term in chunk_terms if term in query_set) / len(chunk_terms)
    return (coverage * 0.75) + (density * 0.25) + min(hit.score, 1.0) * 0.05


def canonical_token_set(tokens: list[str]) -> set[str]:
    canonical: set[str] = set()
    for token in tokens:
        canonical.add(token)
        if len(token) > 3 and token.endswith("s"):
            canonical.add(token[:-1])
    return canonical


class BgeReranker(Reranker):
    def __init__(self) -> None:
        flag_embedding = cast(Any, import_module("FlagEmbedding"))

        self._model = flag_embedding.FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=False)

    async def rerank(self, query: str, hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        pairs = [[query, hit.chunk.text] for hit in hits]
        if not pairs:
            return []
        scores = self._model.compute_score(pairs)
        if isinstance(scores, float):
            scores = [scores]
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
