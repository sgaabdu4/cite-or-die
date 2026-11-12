import pytest
from qdrant_client import QdrantClient

from cite_or_die.core.models import DocumentChunk
from cite_or_die.retrieval.vector_store import QdrantVectorStore, safe_collection_name


def chunk(text: str, embedding: list[float], ordinal: int) -> DocumentChunk:
    return DocumentChunk(
        tenant_id="t1",
        doc_id="d1",
        filename="a.txt",
        text=text,
        ordinal=ordinal,
        embedding=embedding,
    )


@pytest.mark.asyncio()
async def test_qdrant_store_returns_the_nearest_chunk_first() -> None:
    store = QdrantVectorStore("http://localhost:6333", 2)
    store._client = QdrantClient(":memory:")
    await store.upsert("t1", [chunk("near", [1.0, 0.0], 0), chunk("far", [0.0, 1.0], 1)])

    hits = await store.search("t1", [0.9, 0.1], limit=2)

    assert [found.text for found, _score in hits] == ["near", "far"]
    assert hits[0][1] > hits[1][1]


def test_collection_name_replaces_unsafe_characters() -> None:
    assert safe_collection_name("a b/c.d-e_f") == "tenant_a_b_c_d-e_f"
