from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from cite_or_die.core.models import DocumentChunk
from cite_or_die.retrieval.embeddings import tokenize


@dataclass
class TenantBm25Index:
    chunks: list[DocumentChunk] = field(default_factory=list)
    _index: BM25Okapi | None = None

    def rebuild(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks
        corpus = [tokenize(chunk.text) for chunk in chunks]
        self._index = BM25Okapi(corpus) if corpus else None

    def search(self, query: str, limit: int) -> list[tuple[DocumentChunk, float]]:
        if self._index is None:
            return []
        scores = self._index.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: float(item[1]), reverse=True)
        return [(self.chunks[index], float(score)) for index, score in ranked[:limit]]


class Bm25Registry:
    def __init__(self) -> None:
        self._indexes: dict[str, TenantBm25Index] = {}

    def rebuild(self, tenant_id: str, chunks: list[DocumentChunk]) -> None:
        index = self._indexes.setdefault(tenant_id, TenantBm25Index())
        index.rebuild(chunks)

    def search(self, tenant_id: str, query: str, limit: int) -> list[tuple[DocumentChunk, float]]:
        return self._indexes.get(tenant_id, TenantBm25Index()).search(query, limit)
