import asyncio
import sqlite3

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from cite_or_die.core.models import (
    AuthContext,
    ChatRequest,
    Citation,
    Claim,
    DocumentChunk,
    DocumentRecord,
    GuardrailStatus,
    LLMAnswer,
    ProviderConfigInput,
    Role,
)
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.providers.base import Provider, ProviderResponse
from cite_or_die.security.pseudonymization import pseudonym_scope_operation_lock
from cite_or_die.security.walls import (
    MatterMismatchError,
    OutputScopeError,
    TamperDetectedError,
    WallBreachError,
    verify_citation_scope,
    verify_retrieval_scope,
)


class RecordingProvider(Provider):
    name = "recording"

    def __init__(self) -> None:
        self.questions: list[str] = []
        self.chunk_texts: list[list[str]] = []

    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        self.questions.append(question)
        self.chunk_texts.append([chunk.text for chunk in chunks])
        chunk = chunks[0]
        quote = chunk.text.split(". ", 1)[0] + "."
        answer = LLMAnswer(
            answer=f"Based on the retrieved source, {quote}",
            claims=[
                Claim(
                    text=f"Based on the retrieved source, {quote}",
                    citations=[
                        Citation(
                            chunk_id=chunk.chunk_id,
                            doc_id=chunk.doc_id,
                            filename=chunk.filename,
                            tenant_id=chunk.tenant_id,
                            matter_id=chunk.matter_id,
                            page=chunk.page,
                            quote=quote,
                        )
                    ],
                )
            ],
        )
        return ProviderResponse(
            answer=answer,
            model_provider=self.name,
            model_version=model_version,
        )


class QuerySupportingProvider(RecordingProvider):
    async def generate(
        self,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        self.questions.append(question)
        self.chunk_texts.append([chunk.text for chunk in chunks])
        chunk = chunks[0]
        target = next(
            (part for part in question.split() if part.startswith("<CUSTOMER_")),
            "",
        )
        sentences = [sentence.strip() for sentence in chunk.text.split(".") if sentence.strip()]
        quote = next(
            (sentence for sentence in sentences if target and target in sentence),
            sentences[0],
        )
        quote = f"{quote}."
        claim_text = f"Based on the retrieved source, {quote}"
        answer = LLMAnswer(
            answer=claim_text,
            claims=[
                Claim(
                    text=claim_text,
                    citations=[
                        Citation(
                            chunk_id=chunk.chunk_id,
                            doc_id=chunk.doc_id,
                            filename=chunk.filename,
                            tenant_id=chunk.tenant_id,
                            matter_id=chunk.matter_id,
                            page=chunk.page,
                            quote=quote,
                        )
                    ],
                )
            ],
        )
        return ProviderResponse(
            answer=answer,
            model_provider=self.name,
            model_version=model_version,
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


@pytest.mark.asyncio()
async def test_entity_names_are_pseudonymized_before_retrieval_and_generation(settings) -> None:
    provider = RecordingProvider()
    service = CiteOrDieService(settings, provider=provider)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )

    upload = await service.upload(
        ctx,
        "customer.txt",
        "text/plain",
        (
            b"Acme Ltd generated GBP 12m revenue from Barclays. "
            b"Jane Smith approved the contract."
        ),
    )
    chunks = service.repository.list_chunks("tenant-a", "matter-a")
    entity_map = service.repository.list_pii_entities(upload.document.doc_id)
    response = await service.chat(
        ctx,
        ChatRequest(question="What revenue came from Barclays?"),
    )
    audit_payloads = "\n".join(str(event["payload_json"]) for event in service.audit.recent())

    assert provider.questions[-1] == "What revenue came from <CUSTOMER_001>?"
    assert provider.chunk_texts[-1]
    provider_context = "\n".join(provider.chunk_texts[-1])
    assert "<TARGET_COMPANY>" in provider_context
    assert "<CUSTOMER_001>" in provider_context
    assert "<PERSON_001>" in provider_context
    assert "GBP 12m" in provider_context
    assert all("Acme Ltd" not in chunk.text for chunk in chunks)
    assert all("Barclays" not in chunk.text for chunk in chunks)
    assert all("Jane Smith" not in chunk.text for chunk in chunks)
    assert "Barclays" not in response.answer
    assert "Acme Ltd" not in audit_payloads
    assert "Barclays" not in audit_payloads
    assert "Jane Smith" not in audit_payloads
    assert {entity.entity_type for entity in entity_map} >= {
        "TARGET_COMPANY",
        "CUSTOMER",
        "PERSON",
    }


@pytest.mark.asyncio()
async def test_chat_waits_for_in_scope_pseudonym_ingest_operation(settings) -> None:
    provider = RecordingProvider()
    service = CiteOrDieService(settings, provider=provider)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )
    await service.upload(
        ctx,
        "customer.txt",
        "text/plain",
        b"Acme Ltd generated GBP 12m revenue from Barclays.",
    )

    async with pseudonym_scope_operation_lock(settings, "tenant-a", "matter-a"):
        chat_task = asyncio.create_task(
            service.chat(ctx, ChatRequest(question="What revenue came from Barclays?"))
        )
        await asyncio.sleep(0)
        assert not chat_task.done()

    await chat_task
    assert provider.questions


@pytest.mark.asyncio()
async def test_legacy_raw_chunks_are_pseudonymized_before_generation(settings) -> None:
    provider = RecordingProvider()
    service = CiteOrDieService(settings, provider=provider)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )
    document = DocumentRecord(
        tenant_id="tenant-a",
        matter_id="matter-a",
        filename="legacy.txt",
        content_type="text/plain",
        sha256="legacy-sha",
    )
    chunk = DocumentChunk(
        tenant_id="tenant-a",
        matter_id="matter-a",
        doc_id=document.doc_id,
        filename=document.filename,
        text=(
            "Acme Ltd generated GBP 12m revenue from Barclays. "
            "Jane Smith approved the contract."
        ),
        ordinal=0,
    )
    embedded = await service.retrieval.index_chunks("tenant-a", [chunk], "matter-a")
    service.repository.save_document(document, embedded, [])

    response = await service.chat(
        ctx,
        ChatRequest(question="What revenue came from Barclays?"),
    )
    provider_context = "\n".join(provider.chunk_texts[-1])

    assert provider.questions[-1] == "What revenue came from <CUSTOMER_001>?"
    assert "<TARGET_COMPANY>" in provider_context
    assert "<CUSTOMER_001>" in provider_context
    assert "<PERSON_001>" in provider_context
    assert "Acme Ltd" not in provider_context
    assert "Barclays" not in provider_context
    assert "Jane Smith" not in provider_context
    assert "Barclays" not in response.answer


@pytest.mark.asyncio()
async def test_hosted_transient_pseudonyms_do_not_escape_citation_quotes(settings) -> None:
    provider = QuerySupportingProvider()
    hosted_settings = settings.model_copy(update={"llm_provider": "openai"})
    service = CiteOrDieService(hosted_settings, provider=provider)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )
    upload = await service.upload(
        ctx,
        "metrics.txt",
        "text/plain",
        b"New Logo revenue was GBP 3m. Barclays revenue was GBP 12m.",
    )

    response = await service.chat(ctx, ChatRequest(question="Barclays revenue?"))
    evidence = (
        service.settings.uploads_path / "evidence" / f"{upload.document.doc_id}.txt"
    ).read_text(encoding="utf-8")
    provider_context = "\n".join(provider.chunk_texts[-1])

    assert provider.questions[-1] == "<CUSTOMER_002> revenue?"
    assert "<CUSTOMER_001> revenue was GBP 3m." in provider_context
    assert "<CUSTOMER_002> revenue was GBP 12m." in provider_context
    assert "Barclays" not in provider_context
    assert response.guardrails[-1].status == GuardrailStatus.accepted
    assert response.citations[0].quote == "Barclays revenue was GBP 12m."
    assert response.citations[0].quote in evidence


@pytest.mark.asyncio()
async def test_hosted_generation_rejects_residual_unpseudonymized_entities(settings) -> None:
    provider = RecordingProvider()
    hosted_settings = settings.model_copy(
        update={
            "llm_provider": "openai",
            "openai_api_key": SecretStr("openai-key"),
        }
    )
    service = CiteOrDieService(hosted_settings, provider=provider)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )
    document = DocumentRecord(
        tenant_id="tenant-a",
        matter_id="matter-a",
        filename="legacy.txt",
        content_type="text/plain",
        sha256="legacy-sha",
    )
    chunk = DocumentChunk(
        tenant_id="tenant-a",
        matter_id="matter-a",
        doc_id=document.doc_id,
        filename=document.filename,
        text="Barclays cancelled the renewal.",
        ordinal=0,
    )
    embedded = await service.retrieval.index_chunks("tenant-a", [chunk], "matter-a")
    service.repository.save_document(document, embedded, [])

    with pytest.raises(HTTPException) as exc:
        await service.chat(
            ctx,
            ChatRequest(question="Participants: Jane Smith and John Doe"),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Hosted generation context contains unprotected entity names."
    assert provider.questions == []


@pytest.mark.asyncio()
async def test_chat_translates_runtime_provider_policy_errors(settings) -> None:
    prod_settings = settings.model_copy(
        update={
            "app_env": "prod",
            "allow_hosted_llm": False,
            "llm_provider": "fake",
        }
    )
    service = CiteOrDieService(prod_settings)
    service.runtime_config.save(
        "tenant-a",
        ProviderConfigInput(
            llm_provider="openai",
            llm_model="gpt-test-1",
            llm_api_key=SecretStr("sk-test-runtime-provider"),
        ),
        actor="alice",
    )
    service.invalidate_runtime_config("tenant-a")
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )

    with pytest.raises(HTTPException) as exc:
        await service.chat(ctx, ChatRequest(question="What is revenue?"))

    assert exc.value.status_code == 400
    assert exc.value.detail == (
        "Hosted LLM providers receive the question and retrieved chunks. "
        "Set CITE_OR_DIE_ALLOW_HOSTED_LLM=true to enable this in production."
    )


@pytest.mark.asyncio()
async def test_repository_lists_chunks_for_selected_documents(settings) -> None:
    service = CiteOrDieService(settings)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-a", subject="alice", roles=[Role.admin]
    )
    excluded = await service.upload(
        ctx,
        "excluded.txt",
        "text/plain",
        b"Excluded customer concentration source.",
    )
    included = await service.upload(
        ctx,
        "included.txt",
        "text/plain",
        b"Included FY26 revenue source.",
    )

    chunks = service.repository.list_chunks(
        "tenant-a",
        "matter-a",
        doc_ids=[included.document.doc_id],
    )

    assert chunks
    assert {chunk.doc_id for chunk in chunks} == {included.document.doc_id}
    assert excluded.document.doc_id not in {chunk.doc_id for chunk in chunks}
    assert service.repository.list_chunks("tenant-a", "matter-a", doc_ids=[]) == []


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
