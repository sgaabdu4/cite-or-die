from fastapi import HTTPException

from cite_or_die.auth.authorizer import Authorizer
from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    ChatRequest,
    ChatResponse,
    DocumentChunk,
    GuardrailDecision,
    GuardrailStatus,
    ProviderConfigStored,
    UploadResponse,
)
from cite_or_die.ingest.pipeline import IngestPipeline
from cite_or_die.observability.metrics import FAITHFULNESS_FAILURES, TOKENS
from cite_or_die.providers.base import Provider
from cite_or_die.providers.factory import make_provider, make_provider_from_override
from cite_or_die.retrieval.service import RetrievalService
from cite_or_die.security.citation_verifier import CitationVerifier
from cite_or_die.security.input_guard import (
    normalize_user_text,
    scan_retrieved_chunks,
    scan_user_text,
)
from cite_or_die.security.runtime_config import RuntimeConfigStore
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
        self.runtime_config = RuntimeConfigStore(settings)
        self._provider_cache: dict[str, Provider] = {}
        self._retrieval_cache: dict[str, RetrievalService] = {}

    def resolve_provider(self, tenant_id: str) -> Provider:
        override = self.runtime_config.load(tenant_id)
        if override is None:
            return self.provider
        cache_key = self._override_cache_key(tenant_id, override)
        if cache_key not in self._provider_cache:
            self._provider_cache[cache_key] = make_provider_from_override(
                self.settings, override
            )
        return self._provider_cache[cache_key]

    def resolve_retrieval(self, tenant_id: str) -> RetrievalService:
        override = self.runtime_config.load(tenant_id)
        if override is None:
            return self.retrieval
        if (
            override.embedding_provider == self.settings.embedding_provider
            and override.embedding_dim == self.settings.embedding_dim
            and override.reranker_provider == self.settings.reranker_provider
        ):
            return self.retrieval
        cache_key = self._override_cache_key(tenant_id, override)
        if cache_key not in self._retrieval_cache:
            overlay = self.settings.model_copy(
                update={
                    "embedding_provider": override.embedding_provider,
                    "embedding_dim": override.embedding_dim,
                    "reranker_provider": override.reranker_provider,
                }
            )
            self._retrieval_cache[cache_key] = RetrievalService(overlay)
        return self._retrieval_cache[cache_key]

    def invalidate_runtime_config(self, tenant_id: str) -> None:
        self.runtime_config.invalidate(tenant_id)
        prefix = f"{tenant_id}:"
        for key in list(self._provider_cache):
            if key.startswith(prefix):
                self._provider_cache.pop(key, None)
        for key in list(self._retrieval_cache):
            if key.startswith(prefix):
                self._retrieval_cache.pop(key, None)

    @staticmethod
    def _override_cache_key(tenant_id: str, override: ProviderConfigStored) -> str:
        return f"{tenant_id}:{override.configured_at.isoformat()}"

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
        retrieval = self.resolve_retrieval(effective_tenant)
        pipeline = IngestPipeline(self.settings, self.repository, retrieval)
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

        provider = self.resolve_provider(tenant_id)
        retrieval = self.resolve_retrieval(tenant_id)
        override = self.runtime_config.load(tenant_id)
        effective_model = override.llm_model if override else self.settings.llm_model

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
                model_provider=provider.name,
                model_version=effective_model,
                tenant_id=tenant_id,
                matter_id=matter_id,
            )

        chunks = self.repository.list_chunks(tenant_id, matter_id)
        retrieval.rebuild_sparse(tenant_id, chunks, matter_id)
        top_k = request.top_k or self.settings.retrieval_top_k
        hits = await retrieval.retrieve(tenant_id, question, top_k, matter_id)
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
                model_provider=provider.name,
                model_version=effective_model,
                tenant_id=tenant_id,
                matter_id=matter_id,
            )

        provider_response = await provider.generate(question, retrieved, effective_model)
        TOKENS.labels(
            tenant_id,
            provider_response.model_provider,
            provider_response.model_version,
        ).inc(_approx_token_count(question, retrieved))
        verified_answer, citation_decision = self.verifier.verify(
            provider_response.answer, retrieved
        )
        guardrails.append(citation_decision)
        if citation_decision.status != GuardrailStatus.accepted:
            FAITHFULNESS_FAILURES.labels(tenant_id).inc()
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


def _approx_token_count(question: str, chunks: list[DocumentChunk]) -> int:
    chunk_terms = sum(len(chunk.text.split()) for chunk in chunks)
    return max(1, len(question.split()) + chunk_terms)
