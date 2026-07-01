import asyncio
import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentRecord, UploadResponse
from cite_or_die.ingest.chunker import chunk_pages
from cite_or_die.ingest.loaders import load_document
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.security.pii import redact_pii_pages
from cite_or_die.security.pseudonymization import (
    persist_pseudonymized_pages_for_matter,
    prepare_pseudonymized_pages_for_matter,
    restore_pseudonym_map_for_matter,
    snapshot_pseudonym_map_for_matter,
)
from cite_or_die.storage.repository import Repository

_PSEUDONYM_INGEST_LOCKS: dict[tuple[str, str, str], asyncio.Lock] = {}


class IngestPipeline:
    def __init__(self, settings: Settings, repository: Repository, retrieval: RetrievalService):
        self.settings = settings
        self.repository = repository
        self.retrieval = retrieval

    async def ingest(
        self,
        tenant_id: str,
        matter_id: str,
        filename: str,
        content_type: str,
        data: bytes,
    ) -> UploadResponse:
        max_bytes = self.settings.max_upload_mb * 1024 * 1024
        if len(data) > max_bytes:
            raise ValueError(f"upload exceeds {self.settings.max_upload_mb} MB")

        pages = load_document(filename, content_type, data)
        if not pages:
            raise ValueError("document has no extractable text")

        async with _pseudonym_map_ingest_lock(self.settings, tenant_id, matter_id):
            pseudonymized = prepare_pseudonymized_pages_for_matter(
                pages,
                settings=self.settings,
                tenant_id=tenant_id,
                matter_id=matter_id,
            )
            pages = pseudonymized.pages
            pages, pii_entities_redacted, pii_entities = redact_pii_pages(pages)

            document = DocumentRecord(
                tenant_id=tenant_id,
                matter_id=matter_id,
                filename=filename,
                content_type=content_type,
                sha256=hashlib.sha256(data).hexdigest(),
                page_count=max((page or 0) for _, page in pages) or None,
            )
            stored_paths: list[Path] = []
            embedded = []
            map_snapshot: bytes | None = None
            map_saved = False
            try:
                stored_paths.append(self._store_source_file(document.doc_id, filename, data))
                stored_paths.append(self._store_evidence_file(document.doc_id, pages))
                chunks = chunk_pages(
                    document,
                    pages,
                    self.settings.chunk_size,
                    self.settings.chunk_overlap,
                )
                embedded = await self.retrieval.index_chunks(tenant_id, chunks, matter_id)
                if pseudonymized.changed:
                    map_snapshot = snapshot_pseudonym_map_for_matter(
                        settings=self.settings,
                        tenant_id=tenant_id,
                        matter_id=matter_id,
                    )
                persist_pseudonymized_pages_for_matter(
                    pseudonymized,
                    settings=self.settings,
                    tenant_id=tenant_id,
                    matter_id=matter_id,
                )
                map_saved = pseudonymized.changed
                self.repository.save_document(
                    document,
                    embedded,
                    [*pseudonymized.entities, *pii_entities],
                )
                self.retrieval.rebuild_sparse(
                    tenant_id, self.repository.list_chunks(tenant_id, matter_id), matter_id
                )
            except Exception:
                self.repository.delete_document(tenant_id, matter_id, document.doc_id)
                if embedded:
                    await self.retrieval.delete_chunks(
                        tenant_id,
                        [chunk.chunk_id for chunk in embedded],
                        matter_id,
                    )
                    self.retrieval.rebuild_sparse(
                        tenant_id, self.repository.list_chunks(tenant_id, matter_id), matter_id
                    )
                if map_saved:
                    restore_pseudonym_map_for_matter(
                        map_snapshot,
                        settings=self.settings,
                        tenant_id=tenant_id,
                        matter_id=matter_id,
                    )
                for path in stored_paths:
                    try:
                        path.unlink()
                    except FileNotFoundError:
                        pass
                raise
            return UploadResponse(
                document=document,
                chunks=len(embedded),
                pii_entities_redacted=pseudonymized.count + pii_entities_redacted,
            )

    def _store_source_file(self, doc_id: str, filename: str, data: bytes) -> Path:
        self.settings.uploads_path.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower()
        if not suffix or len(suffix) > 16 or not suffix[1:].isalnum():
            suffix = ".bin"
        path = self.settings.uploads_path / f"{doc_id}{suffix}"
        path.write_bytes(data)
        return path

    def _store_evidence_file(self, doc_id: str, pages: list[tuple[str, int | None]]) -> Path:
        evidence_path = self.settings.uploads_path / "evidence" / f"{doc_id}.txt"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(_evidence_text(pages), encoding="utf-8")
        return evidence_path


@asynccontextmanager
async def _pseudonym_map_ingest_lock(
    settings: Settings,
    tenant_id: str,
    matter_id: str,
) -> AsyncIterator[None]:
    key = (str(settings.data_dir.resolve()), tenant_id, matter_id)
    lock = _PSEUDONYM_INGEST_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _PSEUDONYM_INGEST_LOCKS[key] = lock
    async with lock:
        yield


def _evidence_text(pages: list[tuple[str, int | None]]) -> str:
    parts = []
    for text, page in pages:
        body = text.strip()
        if not body:
            continue
        if page is None:
            parts.append(body)
        else:
            parts.append(f"Page {page}\n{body}")
    return "\n\n".join(parts)
