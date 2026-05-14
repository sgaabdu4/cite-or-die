import hashlib
from pathlib import Path

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentRecord, UploadResponse
from cite_or_die.ingest.chunker import chunk_pages
from cite_or_die.ingest.loaders import load_document
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.security.pii import redact_pii_pages
from cite_or_die.storage.repository import Repository


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
        pages, pii_entities_redacted, pii_entities = redact_pii_pages(pages)

        document = DocumentRecord(
            tenant_id=tenant_id,
            matter_id=matter_id,
            filename=filename,
            content_type=content_type,
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=max((page or 0) for _, page in pages) or None,
        )
        self._store_source_file(document.doc_id, filename, data)
        chunks = chunk_pages(
            document,
            pages,
            self.settings.chunk_size,
            self.settings.chunk_overlap,
        )
        embedded = await self.retrieval.index_chunks(tenant_id, chunks, matter_id)
        self.repository.save_document(document, embedded, pii_entities)
        self.retrieval.rebuild_sparse(
            tenant_id, self.repository.list_chunks(tenant_id, matter_id), matter_id
        )
        return UploadResponse(
            document=document,
            chunks=len(embedded),
            pii_entities_redacted=pii_entities_redacted,
        )

    def _store_source_file(self, doc_id: str, filename: str, data: bytes) -> None:
        self.settings.uploads_path.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower()
        if not suffix or len(suffix) > 16 or not suffix[1:].isalnum():
            suffix = ".bin"
        (self.settings.uploads_path / f"{doc_id}{suffix}").write_bytes(data)
