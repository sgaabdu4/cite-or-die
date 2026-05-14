import re

from cite_or_die.core.models import DocumentChunk, DocumentRecord

SPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    return SPACE.sub(" ", text).strip()


def chunk_pages(
    document: DocumentRecord,
    pages: list[tuple[str, int | None]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    ordinal = 0
    stride = max(1, chunk_size - chunk_overlap)

    for text, page in pages:
        cleaned = clean_text(text)
        for start in range(0, len(cleaned), stride):
            part = cleaned[start : start + chunk_size].strip()
            if not part:
                continue
            chunks.append(
                DocumentChunk(
                    tenant_id=document.tenant_id,
                    doc_id=document.doc_id,
                    filename=document.filename,
                    page=page,
                    ordinal=ordinal,
                    text=part,
                )
            )
            ordinal += 1
            if start + chunk_size >= len(cleaned):
                break
    return chunks
