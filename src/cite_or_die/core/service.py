from fastapi import HTTPException

from cite_or_die.auth.authorizer import Authorizer
from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    ChatRequest,
    ChatResponse,
    GuardrailDecision,
    GuardrailStatus,
    UploadResponse,
)
from cite_or_die.ingest.pipeline import IngestPipeline
from cite_or_die.providers.base import Provider
from cite_or_die.providers.factory import make_provider
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.security.citation_verifier import CitationVerifier
from cite_or_die.security.input_guard import (
    normalize_user_text,
    scan_retrieved_chunks,
    scan_user_text,
)
from cite_or_die.security.walls import (
    require_matter_scope,
    verify_citation_scope,
    verify_retrieval_scope,
)
from cite_or_die.storage.audit import AuditLog
from cite_or_die.storage.repository import Repository


class CiteOrDieService:
    def __init__(
        self,
        settings: Settings,
        repository: Repository | None = None,
        audit: AuditLog | None = None,
        retrieval: RetrievalService | None = None,
        provider: Provider | None = None,
    ):
        self.settings = settings
        self.repository = repository or Repository(settings.sqlite_path)
        self.audit = audit or AuditLog(settings.sqlite_path)
        self.retrieval = retrieval or RetrievalService(settings)
        self.provider = provider or make_provider(settings)
        self.authorizer = Authorizer()
        self.verifier = CitationVerifier()

    async def upload(
        self,
        ctx: AuthContext,
        filename: str,
        content_type: str,
        data: bytes,
        tenant_id: str | None = None,
        matter_id: str | None = None,
    ) -> UploadResponse:
        effective_tenant = tenant_id or ctx.tenant_id
        effective_matter = matter_id or ctx.matter_id
        self.authorizer.require(ctx, "upload", effective_tenant, effective_matter)
        pipeline = IngestPipeline(self.settings, self.repository, self.retrieval)
        try:
            response = await pipeline.ingest(
                effective_tenant, effective_matter, filename, content_type, data
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        self.audit.append(
            AuditEvent(
                tenant_id=effective_tenant,
                actor=ctx.subject,
                event_type=AuditEventType.upload,
                payload={
                    "doc_id": response.document.doc_id,
                    "matter_id": response.document.matter_id,
                    "filename": response.document.filename,
                    "chunk_count": response.chunks,
                    "pii_entities_redacted": response.pii_entities_redacted,
                },
            )
        )
        return response

    async def chat(self, ctx: AuthContext, request: ChatRequest) -> ChatResponse:
        tenant_id = request.tenant_id or ctx.tenant_id
        matter_id = request.matter_id or ctx.matter_id
        require_matter_scope(ctx.matter_id, matter_id)
        self.authorizer.require(ctx, "chat", tenant_id, matter_id)

        question, normalize_decision = normalize_user_text(request.question)
        injection_decision = scan_user_text(question)
        guardrails: list[GuardrailDecision] = [normalize_decision, injection_decision]
        if injection_decision.status == GuardrailStatus.rejected:
            self._audit_guardrails(ctx, tenant_id, guardrails)
            return ChatResponse(
                answer="Request rejected by input guardrails.",
                claims=[],
                citations=[],
                guardrails=guardrails,
                model_provider=self.provider.name,
                model_version=self.settings.llm_model,
                tenant_id=tenant_id,
                matter_id=matter_id,
            )

        chunks = self.repository.list_chunks(tenant_id, matter_id)
        self.retrieval.rebuild_sparse(tenant_id, chunks, matter_id)
        top_k = request.top_k or self.settings.retrieval_top_k
        hits = await self.retrieval.retrieve(tenant_id, question, top_k, matter_id)
        retrieved = [hit.chunk for hit in hits]
        verify_retrieval_scope(retrieved, tenant_id, matter_id)
        retrieved_decision = scan_retrieved_chunks(retrieved)
        guardrails.append(retrieved_decision)

        self.audit.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.retrieve,
                payload={
                    "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieved],
                    "matter_id": matter_id,
                    "top_k": top_k,
                },
            )
        )
        if retrieved_decision.status == GuardrailStatus.rejected:
            self._audit_guardrails(ctx, tenant_id, guardrails)
            return ChatResponse(
                answer="Request rejected by retrieved-content guardrails.",
                claims=[],
                citations=[],
                guardrails=guardrails,
                model_provider=self.provider.name,
                model_version=self.settings.llm_model,
                tenant_id=tenant_id,
                matter_id=matter_id,
            )

        provider_response = await self.provider.generate(
            question, retrieved, self.settings.llm_model
        )
        verified_answer, citation_decision = self.verifier.verify(
            provider_response.answer, retrieved
        )
        guardrails.append(citation_decision)
        self._audit_guardrails(ctx, tenant_id, guardrails)
        self.audit.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.generate,
                payload={
                    "model_provider": provider_response.model_provider,
                    "model_version": provider_response.model_version,
                    "status": citation_decision.status.value,
                },
            )
        )

        citations = [citation for claim in verified_answer.claims for citation in claim.citations]
        verify_citation_scope(citations, tenant_id, matter_id)
        response = ChatResponse(
            answer=verified_answer.answer,
            claims=verified_answer.claims,
            citations=citations,
            guardrails=guardrails,
            model_provider=provider_response.model_provider,
            model_version=provider_response.model_version,
            tenant_id=tenant_id,
            matter_id=matter_id,
        )
        self.audit.append(
            AuditEvent(
                tenant_id=tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.chat,
                payload={
                    "request_id": response.request_id,
                    "status": "ok",
                    "matter_id": response.matter_id,
                    "model_provider": response.model_provider,
                    "model_version": response.model_version,
                },
            )
        )
        return response

    def _audit_guardrails(
        self, ctx: AuthContext, tenant_id: str, guardrails: list[GuardrailDecision]
    ) -> None:
        for decision in guardrails:
            self.audit.append(
                AuditEvent(
                    tenant_id=tenant_id,
                    actor=ctx.subject,
                    event_type=AuditEventType.guardrail,
                    payload={
                        "guardrail": decision.name,
                        "status": decision.status.value,
                        "reason": decision.reason,
                    },
                )
            )
