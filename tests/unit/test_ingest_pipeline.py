import asyncio
from pathlib import Path

import pytest

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentChunk
from cite_or_die.ingest.pipeline import IngestPipeline
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
