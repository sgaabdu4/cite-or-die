import base64
import math
import re
from abc import ABC, abstractmethod
from typing import Any, cast

from cite_or_die.core.models import DocumentChunk


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left)) or 1.0
    right_norm = math.sqrt(sum(b * b for b in right)) or 1.0
    return numerator / (left_norm * right_norm)


def safe_collection_name(scope: str) -> str:
    encoded = base64.urlsafe_b64encode(scope.encode("utf-8")).decode("ascii").rstrip("=")
    return f"tenant_{len(encoded)}_{encoded}"


def qdrant_collection_scope(scope: str, collection_profile: str) -> str:
    return f"{scope}::embedding::{collection_profile}"


def legacy_qdrant_collection_name(scope: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", scope)
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
    async def delete(self, tenant_id: str, chunk_ids: list[str]) -> None:
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

    async def delete(self, tenant_id: str, chunk_ids: list[str]) -> None:
        delete_ids = set(chunk_ids)
        if not delete_ids:
            return
        self._chunks[tenant_id] = [
            chunk for chunk in self._chunks.get(tenant_id, []) if chunk.chunk_id not in delete_ids
        ]

    async def ready(self) -> bool:
        return True


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, dim: int, collection_profile: str | None = None) -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url)
        self._dim = dim
        self._collection_profile = collection_profile or f"dim:{dim}"

    async def _ensure_collection(self, tenant_id: str) -> str:
        from qdrant_client.models import Distance, VectorParams

        collection = self._collection_name(tenant_id)
        if not self._client.collection_exists(collection):
            vectors_config = VectorParams(size=self._dim, distance=Distance.COSINE)
            legacy = self._legacy_collection_for_current_dim(tenant_id)
            if legacy is None:
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=vectors_config,
                )
            else:
                self._migrate_legacy_collection(legacy, collection, vectors_config)
        return collection

    def _collection_name(self, tenant_id: str) -> str:
        return safe_collection_name(qdrant_collection_scope(tenant_id, self._collection_profile))

    def _legacy_collection_for_current_dim(self, tenant_id: str) -> str | None:
        legacy = legacy_qdrant_collection_name(tenant_id)
        if not self._client.collection_exists(legacy):
            return None
        if self._collection_vector_size(legacy) != self._dim:
            return None
        return legacy

    def _collection_vector_size(self, collection: str) -> int | None:
        try:
            info = self._client.get_collection(collection_name=collection)
        except Exception:
            return None
        config = getattr(info, "config", None)
        params = getattr(config, "params", None)
        vectors = getattr(params, "vectors", None)
        if isinstance(vectors, dict):
            if len(vectors) != 1:
                return None
            vectors = next(iter(vectors.values()))
        size = getattr(vectors, "size", None)
        return size if isinstance(size, int) else None

    def _migrate_legacy_collection(
        self,
        legacy_collection: str,
        collection: str,
        vectors_config: Any,
    ) -> None:
        from qdrant_client.models import PointStruct

        self._client.create_collection(
            collection_name=collection,
            vectors_config=vectors_config,
        )
        offset: Any | None = None
        while True:
            records, offset = self._client.scroll(
                collection_name=legacy_collection,
                limit=256,
                with_payload=True,
                with_vectors=True,
                offset=offset,
            )
            points = []
            for record in records:
                vector = getattr(record, "vector", None)
                if vector is None:
                    continue
                points.append(
                    PointStruct(
                        id=record.id,
                        vector=cast(Any, vector),
                        payload=record.payload or {},
                    )
                )
            if points:
                self._client.upsert(collection_name=collection, points=points)
            if offset is None:
                break

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
        results = self._client.search(
            collection_name=collection, query_vector=embedding, limit=limit
        )
        return [
            (DocumentChunk(**result.payload, embedding=None), result.score)
            for result in results
            if result.payload
        ]

    async def delete(self, tenant_id: str, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        from qdrant_client.models import PointIdsList

        collection = await self._ensure_collection(tenant_id)
        point_ids: list[int | str] = list(chunk_ids)
        self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=point_ids),
        )

    async def ready(self) -> bool:
        try:
            self._client.get_collections()
        except Exception:
            return False
        return True


def make_vector_store(
    backend: str,
    qdrant_url: str,
    dim: int,
    *,
    collection_profile: str | None = None,
) -> VectorStore:
    if backend == "qdrant":
        return QdrantVectorStore(qdrant_url, dim, collection_profile)
    return MemoryVectorStore()
