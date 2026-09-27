import re
import sys
from types import ModuleType, SimpleNamespace

import pytest

from cite_or_die.core.models import DocumentChunk
from cite_or_die.retrieval.service import scope_id
from cite_or_die.retrieval.vector_store import (
    QdrantVectorStore,
    legacy_qdrant_collection_name,
    qdrant_collection_scope,
    safe_collection_name,
)


def test_qdrant_collection_name_does_not_collapse_scope_separators() -> None:
    left = safe_collection_name(scope_id("a_", "b"))
    right = safe_collection_name(scope_id("a", "_b"))

    assert left != right
    assert safe_collection_name("") != safe_collection_name("z")
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", left)
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", right)


def test_qdrant_collection_name_versions_embedding_profile() -> None:
    scope = scope_id("tenant", "matter")
    hash_collection = safe_collection_name(qdrant_collection_scope(scope, "hash:384"))
    bge_collection = safe_collection_name(qdrant_collection_scope(scope, "bge-m3:1024"))

    assert hash_collection != bge_collection
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", hash_collection)
    assert re.fullmatch(r"tenant_[A-Za-z0-9_-]+", bge_collection)


@pytest.mark.asyncio()
async def test_qdrant_migrates_legacy_collection_to_profiled_name(monkeypatch) -> None:
    scope = scope_id("tenant", "matter")
    current = safe_collection_name(qdrant_collection_scope(scope, "hash:2"))
    legacy = legacy_qdrant_collection_name(scope)
    chunk = _chunk()
    fake = _FakeQdrantClient(
        collections={
            legacy: [
                SimpleNamespace(
                    id=chunk.chunk_id,
                    vector=[1.0, 0.0],
                    payload=chunk.model_dump(exclude={"embedding"}),
                )
            ]
        },
        vector_sizes={legacy: 2},
    )
    _install_fake_qdrant(monkeypatch, fake)

    store = QdrantVectorStore("http://qdrant.local", 2, "hash:2")
    results = await store.search(scope, [1.0, 0.0], 3)

    assert current in fake.created
    assert fake.upserted == [current]
    assert fake.searches == [current]
    assert results[0][0].chunk_id == chunk.chunk_id


@pytest.mark.asyncio()
async def test_qdrant_ignores_legacy_collection_with_wrong_dimension(monkeypatch) -> None:
    scope = scope_id("tenant", "matter")
    current = safe_collection_name(qdrant_collection_scope(scope, "hash:2"))
    legacy = legacy_qdrant_collection_name(scope)
    fake = _FakeQdrantClient(
        collections={legacy: []},
        vector_sizes={legacy: 8},
    )
    _install_fake_qdrant(monkeypatch, fake)

    store = QdrantVectorStore("http://qdrant.local", 2, "hash:2")
    results = await store.search(scope, [1.0, 0.0], 3)

    assert fake.created == [current]
    assert fake.upserted == []
    assert fake.searches == [current]
    assert results == []


def _chunk() -> DocumentChunk:
    return DocumentChunk(
        chunk_id="chunk-1",
        tenant_id="tenant",
        matter_id="matter",
        doc_id="doc-1",
        filename="source.txt",
        text="Revenue reached 42 million.",
        ordinal=0,
    )


def _install_fake_qdrant(monkeypatch, fake: "_FakeQdrantClient") -> None:
    qdrant_client = ModuleType("qdrant_client")

    def qdrant_client_factory(*, url: str) -> "_FakeQdrantClient":
        return fake

    qdrant_client.QdrantClient = qdrant_client_factory
    models = ModuleType("qdrant_client.models")
    models.Distance = SimpleNamespace(COSINE="cosine")
    models.VectorParams = _FakeVectorParams
    models.PointStruct = _FakePointStruct
    models.PointIdsList = _FakePointIdsList
    monkeypatch.setitem(sys.modules, "qdrant_client", qdrant_client)
    monkeypatch.setitem(sys.modules, "qdrant_client.models", models)


class _FakeQdrantClient:
    def __init__(
        self,
        *,
        collections: dict[str, list[SimpleNamespace]],
        vector_sizes: dict[str, int],
    ) -> None:
        self.collections = collections
        self.vector_sizes = vector_sizes
        self.created: list[str] = []
        self.upserted: list[str] = []
        self.searches: list[str] = []

    def collection_exists(self, collection: str) -> bool:
        return collection in self.collections

    def create_collection(
        self, *, collection_name: str, vectors_config: "_FakeVectorParams"
    ) -> None:
        self.created.append(collection_name)
        self.collections.setdefault(collection_name, [])
        self.vector_sizes[collection_name] = vectors_config.size

    def get_collection(self, *, collection_name: str) -> SimpleNamespace:
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors=SimpleNamespace(size=self.vector_sizes.get(collection_name))
                )
            )
        )

    def scroll(
        self,
        *,
        collection_name: str,
        limit: int,
        with_payload: bool,
        with_vectors: bool,
        offset: object | None,
    ) -> tuple[list[SimpleNamespace], None]:
        return self.collections.get(collection_name, []), None

    def upsert(self, *, collection_name: str, points: list["_FakePointStruct"]) -> None:
        self.upserted.append(collection_name)
        self.collections.setdefault(collection_name, []).extend(
            [
                SimpleNamespace(id=point.id, vector=point.vector, payload=point.payload)
                for point in points
            ]
        )

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        limit: int,
    ) -> list[SimpleNamespace]:
        self.searches.append(collection_name)
        return [
            SimpleNamespace(payload=point.payload, score=1.0)
            for point in self.collections.get(collection_name, [])[:limit]
        ]


class _FakeVectorParams:
    def __init__(self, *, size: int, distance: str) -> None:
        self.size = size
        self.distance = distance


class _FakePointStruct:
    def __init__(self, *, id: str, vector: list[float], payload: dict[str, object]) -> None:
        self.id = id
        self.vector = vector
        self.payload = payload


class _FakePointIdsList:
    def __init__(self, *, points: list[int | str]) -> None:
        self.points = points
