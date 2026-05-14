import sqlite3

import pytest

from cite_or_die.core.models import AuthContext, ChatRequest, Citation, DocumentChunk, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.security.walls import (
    MatterMismatchError,
    OutputScopeError,
    TamperDetectedError,
    WallBreachError,
    verify_citation_scope,
    verify_retrieval_scope,
)


@pytest.mark.asyncio()
async def test_matter_retrieval_context_and_output_stay_scoped(settings) -> None:
    service = CiteOrDieService(settings)
    ctx_alpha = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="alice", roles=[Role.admin]
    )
    ctx_beta = AuthContext(
        tenant_id="tenant-a", matter_id="matter-beta", subject="alice", roles=[Role.admin]
    )
    await service.upload(
        ctx_alpha,
        "alpha.txt",
        "text/plain",
        b"Alpha matter settlement reserve is 31 million.",
    )
    await service.upload(
        ctx_beta,
        "beta.txt",
        "text/plain",
        b"Beta matter settlement reserve is 9 million.",
    )

    beta_hits = await service.retrieval.retrieve(
        "tenant-a", "What is the settlement reserve?", top_k=4, matter_id="matter-beta"
    )
    response = await service.chat(
        ctx_beta,
        ChatRequest(question="What is the settlement reserve?", matter_id="matter-beta"),
    )

    assert beta_hits
    assert all(hit.chunk.matter_id == "matter-beta" for hit in beta_hits)
    assert "Beta matter" in response.answer
    assert "Alpha matter" not in response.answer
    assert all(citation.matter_id == "matter-beta" for citation in response.citations)


@pytest.mark.asyncio()
async def test_cross_matter_session_request_is_rejected(settings) -> None:
    service = CiteOrDieService(settings)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="alice", roles=[Role.admin]
    )

    with pytest.raises(MatterMismatchError):
        await service.chat(
            ctx,
            ChatRequest(question="What is the reserve?", matter_id="matter-beta"),
        )


@pytest.mark.asyncio()
async def test_pii_is_redacted_before_embedding_and_retrieval(settings) -> None:
    service = CiteOrDieService(settings)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )

    upload = await service.upload(
        ctx,
        "pii.txt",
        "text/plain",
        b"Contact jane.doe@example.com about the acquisition reserve.",
    )
    chunks = service.repository.list_chunks("tenant-a", "matter-a")
    entity_map = service.repository.list_pii_entities(upload.document.doc_id)
    response = await service.chat(
        ctx,
        ChatRequest(question="Who should be contacted about the acquisition reserve?"),
    )

    assert upload.pii_entities_redacted == 1
    assert entity_map[0].entity_type == "EMAIL_ADDRESS"
    assert entity_map[0].replacement == "<EMAIL>"
    assert all("jane.doe@example.com" not in chunk.text for chunk in chunks)
    assert "jane.doe@example.com" not in response.answer


def test_audit_chain_tamper_raises(settings) -> None:
    service = CiteOrDieService(settings)
    service.audit.append_event(
        tenant_id="tenant-a",
        actor="alice",
        event_type="chat",
        payload={"request_id": "req-1"},
    )

    with sqlite3.connect(settings.sqlite_path) as conn:
        conn.execute(
            "UPDATE audit_events SET payload_json = ? WHERE id = 1",
            ('{"request_id":"x"}',),
        )

    with pytest.raises(TamperDetectedError):
        service.audit.verify_audit_chain()


def test_wall_helpers_raise_specific_exception_types() -> None:
    chunk = DocumentChunk(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        doc_id="doc-1",
        filename="alpha.txt",
        text="Alpha text",
        ordinal=0,
    )
    citation = Citation(
        chunk_id=chunk.chunk_id,
        doc_id=chunk.doc_id,
        filename=chunk.filename,
        tenant_id=chunk.tenant_id,
        matter_id=chunk.matter_id,
        quote="Alpha",
    )

    with pytest.raises(WallBreachError):
        verify_retrieval_scope([chunk], "tenant-a", "matter-beta")
    with pytest.raises(OutputScopeError):
        verify_citation_scope([citation], "tenant-a", "matter-beta")
