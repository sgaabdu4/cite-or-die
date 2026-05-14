import json
import sqlite3
from pathlib import Path

from cite_or_die.core.models import DocumentChunk, DocumentRecord


class Repository:
    """Tenant-aware local metadata and chunk store."""

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    matter_id TEXT NOT NULL DEFAULT 'm_default',
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    page_count INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    matter_id TEXT NOT NULL DEFAULT 'm_default',
                    doc_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    page INTEGER,
                    ordinal INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    embedding_json TEXT,
                    FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tenant ON chunks(tenant_id)")
            self._ensure_column(conn, "documents", "matter_id", "TEXT NOT NULL DEFAULT 'm_default'")
            self._ensure_column(conn, "chunks", "matter_id", "TEXT NOT NULL DEFAULT 'm_default'")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_tenant_matter
                ON chunks(tenant_id, matter_id)
                """
            )

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def save_document(self, document: DocumentRecord, chunks: list[DocumentChunk]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    doc_id, tenant_id, matter_id, filename, content_type,
                    sha256, page_count, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.doc_id,
                    document.tenant_id,
                    document.matter_id,
                    document.filename,
                    document.content_type,
                    document.sha256,
                    document.page_count,
                    document.created_at.isoformat(),
                ),
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO chunks (
                    chunk_id, tenant_id, matter_id, doc_id, filename, page, ordinal,
                    text, embedding_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        chunk.chunk_id,
                        chunk.tenant_id,
                        chunk.matter_id,
                        chunk.doc_id,
                        chunk.filename,
                        chunk.page,
                        chunk.ordinal,
                        chunk.text,
                        json.dumps(chunk.embedding) if chunk.embedding else None,
                    )
                    for chunk in chunks
                ],
            )

    def list_chunks(self, tenant_id: str, matter_id: str | None = None) -> list[DocumentChunk]:
        with self._connect() as conn:
            if matter_id is None:
                rows = conn.execute(
                    "SELECT * FROM chunks WHERE tenant_id = ? ORDER BY doc_id, ordinal",
                    (tenant_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM chunks
                    WHERE tenant_id = ? AND matter_id = ?
                    ORDER BY doc_id, ordinal
                    """,
                    (tenant_id, matter_id),
                ).fetchall()
        chunks: list[DocumentChunk] = []
        for row in rows:
            chunks.append(
                DocumentChunk(
                    chunk_id=row["chunk_id"],
                    tenant_id=row["tenant_id"],
                    matter_id=row["matter_id"],
                    doc_id=row["doc_id"],
                    filename=row["filename"],
                    page=row["page"],
                    ordinal=row["ordinal"],
                    text=row["text"],
                    embedding=json.loads(row["embedding_json"]) if row["embedding_json"] else None,
                )
            )
        return chunks

    def list_documents(self, tenant_id: str, matter_id: str | None = None) -> list[DocumentRecord]:
        with self._connect() as conn:
            if matter_id is None:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE tenant_id = ? ORDER BY created_at DESC",
                    (tenant_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM documents
                    WHERE tenant_id = ? AND matter_id = ?
                    ORDER BY created_at DESC
                    """,
                    (tenant_id, matter_id),
                ).fetchall()
        return [
            DocumentRecord(
                doc_id=row["doc_id"],
                tenant_id=row["tenant_id"],
                matter_id=row["matter_id"],
                filename=row["filename"],
                content_type=row["content_type"],
                sha256=row["sha256"],
                page_count=row["page_count"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
