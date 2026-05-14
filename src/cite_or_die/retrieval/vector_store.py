import math
import re
from abc import ABC, abstractmethod

from cite_or_die.core.models import DocumentChunk


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)


def safe_collection_name(tenant_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", tenant_id)
    return f"tenant_{safe}"


class VectorStore(ABC):
    @abstractmethod
    async def upsert(self, tenant_id: str, chunks: list[DocumentChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search(
        self, tenant_id: str, embedding: list[float], limit: int
    ) -> list[tuple[DocumentChunk, float]]:
        raise NotImplementedError

    @abstractmethod
    async def ready(self) -> bool:
        raise NotImplementedError


class MemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._chunks: dict[str, list[DocumentChunk]] = {}

    async def upsert(self, tenant_id: str, chunks: list[DocumentChunk]) -> None:
        existing = {chunk.chunk_id: chunk for chunk in self._chunks.get(tenant_id, [])}
        existing.update({chunk.chunk_id: chunk for chunk in chunks})
        self._chunks[tenant_id] = list(existing.values())

    async def search(
        self, tenant_id: str, embedding: list[float], limit: int
    ) -> list[tuple[DocumentChunk, float]]:
        scored = [
            (chunk, cosine(embedding, chunk.embedding or []))
            for chunk in self._chunks.get(tenant_id, [])
            if chunk.embedding
        ]
        return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]

    async def ready(self) -> bool:
        return True


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, dim: int) -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url)
        self._dim = dim

    async def _ensure_collection(self, tenant_id: str) -> str:
        from qdrant_client.models import Distance, VectorParams

        collection = safe_collection_name(tenant_id)
        if not self._client.collection_exists(collection):
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )
        return collection

    async def upsert(self, tenant_id: str, chunks: list[DocumentChunk]) -> None:
        from qdrant_client.models import PointStruct

        collection = await self._ensure_collection(tenant_id)
        points = [
            PointStruct(
                id=chunk.chunk_id,
                vector=chunk.embedding or [],
                payload=chunk.model_dump(exclude={"embedding"}),
            )
            for chunk in chunks
        ]
        if points:
            self._client.upsert(collection_name=collection, points=points)

    async def search(
        self, tenant_id: str, embedding: list[float], limit: int
    ) -> list[tuple[DocumentChunk, float]]:
        collection = await self._ensure_collection(tenant_id)
        results = self._client.search(  # type: ignore[attr-defined]  # pyrefly: ignore[missing-attribute]
            collection_name=collection, query_vector=embedding, limit=limit
        )
        return [
            (DocumentChunk(**result.payload, embedding=None), float(result.score))
            for result in results
            if result.payload
        ]

    async def ready(self) -> bool:
        try:
            self._client.get_collections()
        except Exception:
            return False
        return True


def make_vector_store(backend: str, qdrant_url: str, dim: int) -> VectorStore:
    if backend == "qdrant":
        return QdrantVectorStore(qdrant_url, dim)
    return MemoryVectorStore()
