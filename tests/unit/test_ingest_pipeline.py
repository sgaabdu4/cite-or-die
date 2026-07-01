import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.ingest.pipeline import IngestPipeline
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.security.pseudonymization import PseudonymMapStore, pseudonymize_text_for_matter
from cite_or_die.storage.repository import Repository


class FailingRetrieval:
    async def index_chunks(
        self,
        tenant_id: str,
        chunks: list[DocumentChunk],
        matter_id: str = "m_default",
    ) -> list[DocumentChunk]:
        await asyncio.sleep(0)
        raise RuntimeError("index failed")

    def rebuild_sparse(
        self,
        tenant_id: str,
        chunks: list[DocumentChunk],
        matter_id: str = "m_default",
    ) -> None:
        raise AssertionError("rebuild_sparse should not run")


class YieldingRetrieval(RetrievalService):
    async def index_chunks(
        self,
        tenant_id: str,
        chunks: list[DocumentChunk],
        matter_id: str = "m_default",
    ) -> list[DocumentChunk]:
        await asyncio.sleep(0)
        return await super().index_chunks(tenant_id, chunks, matter_id)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
        vector_backend="memory",
        embedding_provider="hash",
        llm_provider="fake",
    )


@pytest.mark.asyncio()
async def test_pseudonym_map_is_not_saved_when_ingest_fails_after_pseudonymization(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    pipeline = IngestPipeline(settings, Repository(settings.sqlite_path), FailingRetrieval())
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"

    with pytest.raises(RuntimeError, match="index failed"):
        await pipeline.ingest(
            "tenant-a",
            "matter-a",
            "customer.txt",
            "text/plain",
            b"Acme Ltd generated GBP 12m revenue from Barclays.",
        )

    assert not map_path.exists()
    assert Repository(settings.sqlite_path).list_documents("tenant-a", "matter-a") == []


@pytest.mark.asyncio()
async def test_ingest_rolls_back_document_when_pseudonym_map_save_fails(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    repository = Repository(settings.sqlite_path)
    retrieval = RetrievalService(settings)
    pipeline = IngestPipeline(settings, repository, retrieval)
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"

    with (
        patch.object(PseudonymMapStore, "save", side_effect=RuntimeError("map save failed")),
        pytest.raises(RuntimeError, match="map save failed"),
    ):
        await pipeline.ingest(
            "tenant-a",
            "matter-a",
            "customer.txt",
            "text/plain",
            b"Acme Ltd generated GBP 12m revenue from Barclays.",
        )

    assert not map_path.exists()
    assert repository.list_documents("tenant-a", "matter-a") == []
    assert repository.list_chunks("tenant-a", "matter-a") == []
    assert await retrieval.retrieve("tenant-a", "Barclays", 5, "matter-a") == []


@pytest.mark.asyncio()
async def test_ingest_rollback_restores_map_and_files_when_cleanup_steps_fail(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    repository = Repository(settings.sqlite_path)
    retrieval = RetrievalService(settings)
    pipeline = IngestPipeline(settings, repository, retrieval)

    await pipeline.ingest(
        "tenant-a",
        "matter-a",
        "barclays.txt",
        "text/plain",
        b"Acme Ltd generated GBP 12m revenue from Barclays.",
    )
    map_path = tmp_path / "tenants" / "tenant-a" / "matters" / "matter-a" / "entities.enc"
    map_before = map_path.read_bytes()
    uploads_before = {
        path.relative_to(settings.uploads_path)
        for path in settings.uploads_path.rglob("*")
        if path.is_file()
    }

    with (
        patch.object(repository, "save_document", side_effect=RuntimeError("commit failed")),
        patch.object(repository, "delete_document", side_effect=RuntimeError("delete failed")),
        patch.object(retrieval, "delete_chunks", side_effect=RuntimeError("vector delete failed")),
        patch.object(retrieval, "rebuild_sparse", side_effect=RuntimeError("sparse failed")),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await pipeline.ingest(
            "tenant-a",
            "matter-a",
            "hsbc.txt",
            "text/plain",
            b"Acme Ltd generated GBP 8m revenue from HSBC.",
        )

    uploads_after = {
        path.relative_to(settings.uploads_path)
        for path in settings.uploads_path.rglob("*")
        if path.is_file()
    }
    assert map_path.read_bytes() == map_before
    assert uploads_after == uploads_before
    assert repository.list_chunks("tenant-a", "matter-a")


@pytest.mark.asyncio()
async def test_ingest_rollback_does_not_clobber_concurrent_pseudonym_map_update(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    repository = Repository(settings.sqlite_path)
    retrieval = RetrievalService(settings)
    pipeline = IngestPipeline(settings, repository, retrieval)

    await pipeline.ingest(
        "tenant-a",
        "matter-a",
        "barclays.txt",
        "text/plain",
        b"Acme Ltd generated GBP 12m revenue from Barclays.",
    )

    def save_then_concurrent_update(*args, **kwargs) -> None:
        pseudonymize_text_for_matter(
            "What revenue came from Lloyds?",
            settings=settings,
            tenant_id="tenant-a",
            matter_id="matter-a",
        )
        raise RuntimeError("commit failed")

    with (
        patch.object(repository, "save_document", side_effect=save_then_concurrent_update),
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await pipeline.ingest(
            "tenant-a",
            "matter-a",
            "hsbc.txt",
            "text/plain",
            b"Acme Ltd generated GBP 8m revenue from HSBC.",
        )

    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    assert mapping.entries["CUSTOMER"]["barclays"] == "<CUSTOMER_001>"
    assert "lloyds" in mapping.entries["CUSTOMER"]


@pytest.mark.asyncio()
async def test_concurrent_ingests_serialize_pseudonym_map_updates(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    repository = Repository(settings.sqlite_path)
    pipeline = IngestPipeline(settings, repository, YieldingRetrieval(settings))

    await asyncio.gather(
        pipeline.ingest(
            "tenant-a",
            "matter-a",
            "barclays.txt",
            "text/plain",
            b"Acme Ltd generated GBP 12m revenue from Barclays.",
        ),
        pipeline.ingest(
            "tenant-a",
            "matter-a",
            "hsbc.txt",
            "text/plain",
            b"Acme Ltd generated GBP 8m revenue from HSBC.",
        ),
    )

    mapping = PseudonymMapStore(settings).load("tenant-a", "matter-a")
    chunks = repository.list_chunks("tenant-a", "matter-a")

    assert mapping.entries["CUSTOMER"]["barclays"] == "<CUSTOMER_001>"
    assert mapping.entries["CUSTOMER"]["hsbc"] == "<CUSTOMER_002>"
    assert any("<CUSTOMER_001>" in chunk.text for chunk in chunks)
    assert any("<CUSTOMER_002>" in chunk.text for chunk in chunks)
