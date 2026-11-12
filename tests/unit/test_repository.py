from datetime import UTC, datetime

from cite_or_die.core.config import Settings
from cite_or_die.core.models import AuditEvent, AuditEventType, DocumentChunk, DocumentRecord
from cite_or_die.storage.audit import AuditLog
from cite_or_die.storage.repository import (
    LIST_CHUNKS_FOR_MATTER,
    LIST_CHUNKS_FOR_TENANT,
    Repository,
)


def document(doc_id: str, tenant_id: str, matter_id: str, day: int) -> DocumentRecord:
    return DocumentRecord(
        doc_id=doc_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        filename=f"{doc_id}.txt",
        content_type="text/plain",
        sha256="a" * 64,
        page_count=3,
        created_at=datetime(2026, 1, day, tzinfo=UTC),
    )


def chunk(doc: DocumentRecord, ordinal: int) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=f"{doc.doc_id}-{ordinal}",
        tenant_id=doc.tenant_id,
        matter_id=doc.matter_id,
        doc_id=doc.doc_id,
        filename=doc.filename,
        page=ordinal,
        ordinal=ordinal,
        text=f"text {ordinal}",
        embedding=[0.5, 1.5] if ordinal == 0 else None,
    )


def test_repository_lists_return_every_stored_field(settings: Settings) -> None:
    repository = Repository(settings.sqlite_path)
    first = document("d1", "t1", "m1", 1)
    second = document("d2", "t1", "m2", 2)
    other = document("d3", "t2", "m1", 3)
    for doc in (first, second, other):
        repository.save_document(doc, [chunk(doc, 1), chunk(doc, 0)])

    assert repository.list_documents("t1") == [second, first]
    assert repository.list_documents("t1", "m1") == [first]
    assert repository.list_chunks("t1", "m2") == [chunk(second, 0), chunk(second, 1)]
    assert repository.list_chunks("t1") == [
        chunk(first, 0),
        chunk(first, 1),
        chunk(second, 0),
        chunk(second, 1),
    ]


def test_audit_recent_returns_every_column_newest_first(settings: Settings) -> None:
    audit = AuditLog(settings.sqlite_path)
    for actor in ("alice", "bob"):
        audit.append(
            AuditEvent(
                tenant_id="t1", actor=actor, event_type=AuditEventType.chat, payload={"n": 1}
            )
        )

    rows = audit.recent(5)

    assert [row["actor"] for row in rows] == ["bob", "alice"]
    assert set(rows[0]) == {
        "id",
        "tenant_id",
        "actor",
        "event_type",
        "payload_json",
        "created_at",
        "previous_hash",
        "event_hash",
    }
    assert rows[0]["previous_hash"] == rows[1]["event_hash"]


def plan_details(repository: Repository, statement: str, parameters: tuple[str, ...]) -> list[str]:
    with repository._connect() as conn:
        rows = conn.execute(f"EXPLAIN QUERY PLAN {statement}", parameters).fetchall()
    return [row["detail"] for row in rows]


def test_chunk_read_for_one_matter_seeks_on_tenant_and_matter(settings: Settings) -> None:
    repository = Repository(settings.sqlite_path)

    details = plan_details(repository, LIST_CHUNKS_FOR_MATTER, ("t1", "m1"))

    assert any(
        "idx_chunks_tenant_matter" in line and "tenant_id=? AND matter_id=?" in line
        for line in details
    ), details


def test_chunk_read_for_one_tenant_seeks_on_tenant(settings: Settings) -> None:
    repository = Repository(settings.sqlite_path)

    details = plan_details(repository, LIST_CHUNKS_FOR_TENANT, ("t1",))

    assert any(
        "USING INDEX idx_chunks_tenant" in line and "tenant_id=?" in line for line in details
    ), details
