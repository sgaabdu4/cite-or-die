import asyncio
from collections import defaultdict

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    DocumentChunk,
    DocumentRecord,
    GuardrailDecision,
    GuardrailStatus,
)
from cite_or_die.core.service import CiteOrDieService, _restore_transient_labels_in_answer
from cite_or_die.diligence.classification import classify_source
from cite_or_die.diligence.cross_reference import build_insights
from cite_or_die.diligence.extraction import extract_from_sources
from cite_or_die.diligence.models import (
    CrossWorkstreamInsight,
    Deal,
    DiligenceKnowledgeBase,
    DiligenceRunResult,
    EvidenceLink,
    Finding,
    ProviderAssistedDiligenceResult,
    ReportDraft,
    SourceDocument,
)
from cite_or_die.diligence.provider_assist import (
    approx_token_count,
    evidence_links_for_provider,
    provider_report_draft,
)
from cite_or_die.diligence.reporting import build_report_drafts
from cite_or_die.diligence.repository import DiligenceRepository
from cite_or_die.diligence.risk import build_findings
from cite_or_die.observability.metrics import FAITHFULNESS_FAILURES, TOKENS
from cite_or_die.providers.base import Provider, ProviderResponse
from cite_or_die.security.input_guard import (
    normalize_user_text,
    scan_retrieved_chunks,
    scan_user_text,
)
from cite_or_die.security.pseudonymization import (
    InvalidPseudonymMapError,
    PseudonymizedChunkContext,
    ResidualPseudonymizationError,
    pseudonym_scope_operation_lock_sync,
    pseudonymize_chunks_for_matter,
    pseudonymize_generation_context_for_matter,
)
from cite_or_die.security.walls import verify_citation_scope, verify_retrieval_scope

_TRANSIENT_PROVIDER_STATUS_CODES = {429, 500, 502, 503, 504}
_PROVIDER_RETRY_DELAYS_SECONDS = (0.25, 0.75)


class DiligenceService:
    """Domain workflow owner for live-deal diligence acceleration."""

    def __init__(
        self,
        settings: Settings,
        *,
        core_service: CiteOrDieService | None = None,
        repository: DiligenceRepository | None = None,
    ):
        self.settings = settings
        self.core_service = core_service or CiteOrDieService(settings)
        self.repository = repository or DiligenceRepository(settings.sqlite_path)

    def create_deal(
        self,
        ctx: AuthContext,
        *,
        name: str,
        target_business: str,
        target_revenue_gbp_m: int,
        horizon_weeks: int,
        source_doc_ids: list[str] | None = None,
    ) -> Deal:
        self.core_service.authorizer.require(ctx, "upload", ctx.tenant_id, ctx.matter_id)
        scoped_doc_ids = self._validate_source_doc_ids(
            ctx.tenant_id,
            ctx.matter_id,
            source_doc_ids or [],
        )
        deal = Deal(
            tenant_id=ctx.tenant_id,
            matter_id=ctx.matter_id,
            name=name,
            target_business=target_business,
            target_revenue_gbp_m=target_revenue_gbp_m,
            horizon_weeks=horizon_weeks,
            source_doc_ids=scoped_doc_ids,
        )
        self.repository.save_deal(deal)
        self._audit(
            ctx,
            deal,
            status="deal_created",
            source_count=0,
            fact_count=0,
            finding_count=0,
            insight_count=0,
            report_count=0,
        )
        return deal

    def classify_sources(self, ctx: AuthContext, deal_id: str) -> list[SourceDocument]:
        deal = self._require_deal(ctx, deal_id, action="upload")
        documents = self._deal_documents(deal)
        chunks_by_doc = self._chunks_by_doc(
            deal.tenant_id,
            deal.matter_id,
            doc_ids=[document.doc_id for document in documents],
        )
        sources: list[SourceDocument] = []
        for document in documents:
            sample = " ".join(chunk.text for chunk in chunks_by_doc.get(document.doc_id, []))[:4000]
            classification = classify_source(
                filename=document.filename,
                content_type=document.content_type,
                sample_text=sample,
            )
            sources.append(
                SourceDocument(
                    tenant_id=deal.tenant_id,
                    matter_id=deal.matter_id,
                    deal_id=deal.deal_id,
                    doc_id=document.doc_id,
                    filename=document.filename,
                    content_type=document.content_type,
                    document_type=classification.document_type,
                    workstream=classification.workstream,
                    confidence=classification.confidence,
                )
            )
        self.repository.replace_sources(
            sources,
            tenant_id=deal.tenant_id,
            matter_id=deal.matter_id,
            deal_id=deal.deal_id,
        )
        self._audit(
            ctx,
            deal,
            status="sources_classified",
            source_count=len(sources),
            fact_count=0,
            finding_count=0,
            insight_count=0,
            report_count=0,
        )
        return sources

    def run_acceleration(self, ctx: AuthContext, deal_id: str) -> DiligenceRunResult:
        deal = self._require_deal(ctx, deal_id, action="upload")
        if not deal.source_doc_ids:
            sources = self.classify_sources(ctx, deal.deal_id)
        else:
            sources = self.repository.list_sources(deal.tenant_id, deal.matter_id, deal.deal_id)
            if not sources:
                sources = self.classify_sources(ctx, deal.deal_id)

        chunks_by_doc = self._chunks_by_doc(
            deal.tenant_id,
            deal.matter_id,
            doc_ids=[source.doc_id for source in sources],
        )
        source_chunks = [
            (source, chunks_by_doc.get(source.doc_id, []))
            for source in sources
            if chunks_by_doc.get(source.doc_id)
        ]
        scoped_chunks = [chunk for _, chunks in source_chunks for chunk in chunks]
        verify_retrieval_scope(scoped_chunks, deal.tenant_id, deal.matter_id)

        facts, requests, responses = extract_from_sources(source_chunks)
        findings = build_findings(facts, requests)
        insights = build_insights(deal, findings)
        report_drafts = build_report_drafts(deal, findings)
        knowledge_base = DiligenceKnowledgeBase(
            deal=deal,
            sources=sources,
            facts=facts,
            information_requests=requests,
            vendor_responses=responses,
        )
        self.repository.replace_outputs(
            knowledge_base=knowledge_base,
            findings=findings,
            insights=insights,
            reports=report_drafts,
        )
        self._audit(
            ctx,
            deal,
            status="run_completed",
            source_count=len(sources),
            fact_count=len(facts),
            finding_count=len(findings),
            insight_count=len(insights),
            report_count=len(report_drafts),
        )
        return DiligenceRunResult(
            deal=deal,
            knowledge_base=knowledge_base,
            findings=findings,
            insights=insights,
            report_drafts=report_drafts,
            metrics={
                "source_count": len(sources),
                "fact_count": len(facts),
                "finding_count": len(findings),
                "insight_count": len(insights),
                "report_count": len(report_drafts),
                "horizon_weeks": deal.horizon_weeks,
            },
        )

    def list_findings(self, ctx: AuthContext, deal_id: str) -> list[Finding]:
        deal = self._require_deal(ctx, deal_id, action="read")
        return self.repository.list_findings(deal.tenant_id, deal.matter_id, deal.deal_id)

    def list_reports(self, ctx: AuthContext, deal_id: str) -> list[ReportDraft]:
        deal = self._require_deal(ctx, deal_id, action="read")
        return self.repository.list_reports(deal.tenant_id, deal.matter_id, deal.deal_id)

    async def run_provider_assisted_review(
        self, ctx: AuthContext, deal_id: str
    ) -> ProviderAssistedDiligenceResult:
        deal = self._require_deal(ctx, deal_id, action="upload")
        knowledge_base, findings, reports = self._load_completed_run(deal)
        insights = self.repository.list_insights(deal.tenant_id, deal.matter_id, deal.deal_id)
        question, guardrails = self._provider_assist_question(deal)
        if guardrails[-1].status == GuardrailStatus.rejected:
            self.core_service._audit_guardrails(ctx, deal.tenant_id, guardrails)
            self._audit_provider_assist(
                ctx, deal, knowledge_base, findings, insights, reports, "input_rejected"
            )
            raise HTTPException(
                status_code=400,
                detail="provider-assisted review blocked by input guardrails",
            )

        provider = self.core_service.resolve_provider(deal.tenant_id)
        override = self.core_service._load_runtime_override(deal.tenant_id)
        effective_model = override.llm_model if override else self.settings.llm_model
        context = self._provider_generation_context(
            deal,
            question,
            evidence_links_for_provider(knowledge_base, findings, insights, reports),
            require_complete_pseudonymization=self.core_service._hosted_llm_provider(override),
        )
        retrieved = context.chunks
        retrieved_decision = scan_retrieved_chunks(retrieved)
        guardrails.append(retrieved_decision)
        self.core_service.audit.append(
            AuditEvent(
                tenant_id=deal.tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.retrieve,
                payload={
                    "retrieved_chunk_ids": [chunk.chunk_id for chunk in retrieved],
                    "selected_doc_ids": sorted({chunk.doc_id for chunk in retrieved}),
                    "matter_id": deal.matter_id,
                    "top_k": len(retrieved),
                },
            )
        )
        if retrieved_decision.status == GuardrailStatus.rejected:
            self.core_service._audit_guardrails(ctx, deal.tenant_id, guardrails)
            self._audit_provider_assist(
                ctx, deal, knowledge_base, findings, insights, reports, "content_rejected"
            )
            raise HTTPException(
                status_code=400,
                detail="provider-assisted review blocked by retrieved-content guardrails",
            )

        try:
            provider_response = await self._generate_with_provider_retry(
                provider,
                context.question,
                retrieved,
                effective_model,
            )
        except HTTPException:
            self._audit_provider_assist(
                ctx, deal, knowledge_base, findings, insights, reports, "provider_unavailable"
            )
            raise
        answer_for_verification = _restore_transient_labels_in_answer(
            provider_response.answer,
            context.transient_replacements,
        )
        TOKENS.labels(
            deal.tenant_id,
            provider_response.model_provider,
            provider_response.model_version,
        ).inc(approx_token_count(context.question, retrieved))
        verified_answer, citation_decision = self.core_service.verifier.verify(
            answer_for_verification,
            context.citation_chunks,
            context.citation_question,
        )
        guardrails.append(citation_decision)
        if citation_decision.status != GuardrailStatus.accepted:
            FAITHFULNESS_FAILURES.labels(deal.tenant_id).inc()
            self.core_service._audit_guardrails(ctx, deal.tenant_id, guardrails)
            self._audit_generation(ctx, deal, provider_response, citation_decision)
            self._audit_provider_assist(
                ctx, deal, knowledge_base, findings, insights, reports, "citation_rejected"
            )
            raise HTTPException(
                status_code=422,
                detail="provider-assisted review did not return verified citations",
            )

        citations = [citation for claim in verified_answer.claims for citation in claim.citations]
        verify_citation_scope(citations, deal.tenant_id, deal.matter_id)
        report = provider_report_draft(
            deal,
            verified_answer.claims,
            model_provider=provider_response.model_provider,
            model_version=provider_response.model_version,
            evidence_chunk_count=len(retrieved),
        )
        updated_reports = [draft for draft in reports if draft.provider_assistance is None] + [
            report
        ]
        self.repository.replace_reports(
            updated_reports,
            tenant_id=deal.tenant_id,
            matter_id=deal.matter_id,
            deal_id=deal.deal_id,
        )
        self.core_service._audit_guardrails(ctx, deal.tenant_id, guardrails)
        self._audit_generation(ctx, deal, provider_response, citation_decision)
        self._audit_provider_assist(
            ctx,
            deal,
            knowledge_base,
            findings,
            insights,
            updated_reports,
            "provider_assist_completed",
        )
        return ProviderAssistedDiligenceResult(
            deal=deal,
            report_draft=report,
            guardrails=guardrails,
            model_provider=provider_response.model_provider,
            model_version=provider_response.model_version,
            evidence_chunk_count=len(retrieved),
        )

    def _require_deal(self, ctx: AuthContext, deal_id: str, *, action: str) -> Deal:
        deal = self.repository.get_deal(ctx.tenant_id, ctx.matter_id, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail="deal not found")
        self.core_service.authorizer.require(ctx, action, deal.tenant_id, deal.matter_id)
        return deal

    async def _generate_with_provider_retry(
        self,
        provider: Provider,
        question: str,
        chunks: list[DocumentChunk],
        model_version: str,
    ) -> ProviderResponse:
        for attempt in range(len(_PROVIDER_RETRY_DELAYS_SECONDS) + 1):
            try:
                return await provider.generate(question, chunks, model_version)
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code in _TRANSIENT_PROVIDER_STATUS_CODES and attempt < len(
                    _PROVIDER_RETRY_DELAYS_SECONDS
                ):
                    await asyncio.sleep(_PROVIDER_RETRY_DELAYS_SECONDS[attempt])
                    continue
                raise HTTPException(
                    status_code=503,
                    detail=f"provider unavailable: HTTP {status_code}",
                ) from exc
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=503, detail="provider unavailable") from exc
            except (IndexError, KeyError, TypeError, ValueError, ValidationError) as exc:
                raise HTTPException(
                    status_code=502,
                    detail="provider returned an invalid response",
                ) from exc
        raise HTTPException(status_code=503, detail="provider unavailable")

    def _load_completed_run(
        self, deal: Deal
    ) -> tuple[DiligenceKnowledgeBase, list[Finding], list[ReportDraft]]:
        sources = self.repository.list_sources(deal.tenant_id, deal.matter_id, deal.deal_id)
        facts = self.repository.list_facts(deal.tenant_id, deal.matter_id, deal.deal_id)
        requests = self.repository.list_information_requests(
            deal.tenant_id, deal.matter_id, deal.deal_id
        )
        responses = self.repository.list_vendor_responses(
            deal.tenant_id, deal.matter_id, deal.deal_id
        )
        findings = self.repository.list_findings(deal.tenant_id, deal.matter_id, deal.deal_id)
        reports = self.repository.list_reports(deal.tenant_id, deal.matter_id, deal.deal_id)
        if not facts and not findings and not reports:
            raise HTTPException(
                status_code=409,
                detail="run diligence review before provider-assisted review",
            )
        return (
            DiligenceKnowledgeBase(
                deal=deal,
                sources=sources,
                facts=facts,
                information_requests=requests,
                vendor_responses=responses,
            ),
            findings,
            reports,
        )

    def _provider_assist_question(self, deal: Deal) -> tuple[str, list[GuardrailDecision]]:
        question, normalize_decision = normalize_user_text(
            "Create a concise provider-assisted diligence review for a live "
            f"mid-market acquisition with a {deal.horizon_weeks}-week horizon and "
            f"GBP {deal.target_revenue_gbp_m}m target revenue. Focus on commercial, "
            "operational, and financial risks, contradictions, missing information, "
            "and report claims that require analyst review. Use only the supplied "
            "evidence chunks. Every claim must quote the supporting chunk verbatim. "
            "Do not treat this as final sign-off."
        )
        return question, [normalize_decision, scan_user_text(question)]

    def _provider_generation_context(
        self,
        deal: Deal,
        question: str,
        evidence: list[EvidenceLink],
        *,
        require_complete_pseudonymization: bool,
    ) -> PseudonymizedChunkContext:
        if not evidence:
            raise HTTPException(
                status_code=409,
                detail="no cited diligence evidence is available for provider-assisted review",
            )
        evidence_chunk_ids = {link.chunk_id for link in evidence}
        evidence_doc_ids = sorted({link.doc_id for link in evidence})
        try:
            with pseudonym_scope_operation_lock_sync(
                self.settings,
                deal.tenant_id,
                deal.matter_id,
            ):
                chunks = self.core_service.repository.list_chunks(
                    deal.tenant_id,
                    deal.matter_id,
                    doc_ids=evidence_doc_ids,
                )
                chunks = [chunk for chunk in chunks if chunk.chunk_id in evidence_chunk_ids]
                verify_retrieval_scope(chunks, deal.tenant_id, deal.matter_id)
                return pseudonymize_generation_context_for_matter(
                    question,
                    chunks,
                    settings=self.settings,
                    tenant_id=deal.tenant_id,
                    matter_id=deal.matter_id,
                    require_complete_pseudonymization=require_complete_pseudonymization,
                )
        except ResidualPseudonymizationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except InvalidPseudonymMapError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def _audit_generation(
        self,
        ctx: AuthContext,
        deal: Deal,
        provider_response: ProviderResponse,
        citation_decision: GuardrailDecision,
    ) -> None:
        self.core_service.audit.append(
            AuditEvent(
                tenant_id=deal.tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.generate,
                payload={
                    "matter_id": deal.matter_id,
                    "model_provider": provider_response.model_provider,
                    "model_version": provider_response.model_version,
                    "status": citation_decision.status.value,
                },
            )
        )

    def _audit_provider_assist(
        self,
        ctx: AuthContext,
        deal: Deal,
        knowledge_base: DiligenceKnowledgeBase,
        findings: list[Finding],
        insights: list[CrossWorkstreamInsight],
        reports: list[ReportDraft],
        status: str,
    ) -> None:
        self._audit(
            ctx,
            deal,
            status=status,
            source_count=len(knowledge_base.sources),
            fact_count=len(knowledge_base.facts),
            finding_count=len(findings),
            insight_count=len(insights),
            report_count=len(reports),
        )

    def _chunks_by_doc(
        self,
        tenant_id: str,
        matter_id: str,
        *,
        doc_ids: list[str] | None = None,
    ) -> dict[str, list[DocumentChunk]]:
        try:
            with pseudonym_scope_operation_lock_sync(self.settings, tenant_id, matter_id):
                chunks = self.core_service.repository.list_chunks(
                    tenant_id,
                    matter_id,
                    doc_ids=doc_ids,
                )
                verify_retrieval_scope(chunks, tenant_id, matter_id)
                chunks = pseudonymize_chunks_for_matter(
                    chunks,
                    settings=self.settings,
                    tenant_id=tenant_id,
                    matter_id=matter_id,
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except InvalidPseudonymMapError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        grouped: dict[str, list[DocumentChunk]] = defaultdict(list)
        for chunk in chunks:
            grouped[chunk.doc_id].append(chunk)
        return grouped

    def _deal_documents(self, deal: Deal) -> list[DocumentRecord]:
        documents = self.core_service.repository.list_documents(deal.tenant_id, deal.matter_id)
        if not deal.source_doc_ids:
            return documents
        by_id = {document.doc_id: document for document in documents}
        return [by_id[doc_id] for doc_id in deal.source_doc_ids if doc_id in by_id]

    def _validate_source_doc_ids(
        self, tenant_id: str, matter_id: str, source_doc_ids: list[str]
    ) -> list[str]:
        if not source_doc_ids:
            return []
        documents = self.core_service.repository.list_documents(tenant_id, matter_id)
        available = {document.doc_id for document in documents}
        scoped: list[str] = []
        missing: list[str] = []
        seen: set[str] = set()
        for doc_id in source_doc_ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            if doc_id not in available:
                missing.append(doc_id)
            else:
                scoped.append(doc_id)
        if missing:
            raise HTTPException(status_code=404, detail="source document not found")
        return scoped

    def _audit(
        self,
        ctx: AuthContext,
        deal: Deal,
        *,
        status: str,
        source_count: int,
        fact_count: int,
        finding_count: int,
        insight_count: int,
        report_count: int,
    ) -> None:
        self.core_service.audit.append(
            AuditEvent(
                tenant_id=deal.tenant_id,
                actor=ctx.subject,
                event_type=AuditEventType.diligence,
                payload={
                    "deal_id": deal.deal_id,
                    "matter_id": deal.matter_id,
                    "status": status,
                    "source_count": source_count,
                    "fact_count": fact_count,
                    "finding_count": finding_count,
                    "insight_count": insight_count,
                    "report_count": report_count,
                },
            )
        )
