import hashlib

from cite_or_die.core.config import Settings
from cite_or_die.core.models import DocumentRecord, UploadResponse
from cite_or_die.ingest.chunker import chunk_pages
from cite_or_die.ingest.loaders import load_document
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.storage.repository import Repository


class IngestPipeline:
    def __init__(self, settings: Settings, repository: Repository, retrieval: RetrievalService):
        self.settings = settings
        self.repository = repository
        self.retrieval = retrieval

    async def ingest(
        self,
        tenant_id: str,
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

        document = DocumentRecord(
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            sha256=hashlib.sha256(data).hexdigest(),
            page_count=max((page or 0) for _, page in pages) or None,
        )
        chunks = chunk_pages(
            document,
            pages,
            self.settings.chunk_size,
            self.settings.chunk_overlap,
        )
        embedded = await self.retrieval.index_chunks(tenant_id, chunks)
        self.repository.save_document(document, embedded)
        self.retrieval.rebuild_sparse(tenant_id, self.repository.list_chunks(tenant_id))
        return UploadResponse(document=document, chunks=len(embedded))
