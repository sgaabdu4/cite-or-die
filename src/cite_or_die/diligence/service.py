from collections import defaultdict

from fastapi import HTTPException

from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    AuditEvent,
    AuditEventType,
    AuthContext,
    DocumentChunk,
    DocumentRecord,
)
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.diligence.classification import classify_source
from cite_or_die.diligence.cross_reference import build_insights
from cite_or_die.diligence.extraction import extract_from_sources
from cite_or_die.diligence.models import (
    Deal,
    DiligenceKnowledgeBase,
    DiligenceRunResult,
    Finding,
    ReportDraft,
    SourceDocument,
)
from cite_or_die.diligence.reporting import build_report_drafts
from cite_or_die.diligence.repository import DiligenceRepository
from cite_or_die.diligence.risk import build_findings
from cite_or_die.security.walls import verify_retrieval_scope


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
        chunks_by_doc = self._chunks_by_doc(deal.tenant_id, deal.matter_id)
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
        sources = self.repository.list_sources(deal.tenant_id, deal.matter_id, deal.deal_id)
        if not sources:
            sources = self.classify_sources(ctx, deal.deal_id)

        chunks_by_doc = self._chunks_by_doc(deal.tenant_id, deal.matter_id)
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

    def _require_deal(self, ctx: AuthContext, deal_id: str, *, action: str) -> Deal:
        deal = self.repository.get_deal(ctx.tenant_id, ctx.matter_id, deal_id)
        if deal is None:
            raise HTTPException(status_code=404, detail="deal not found")
        self.core_service.authorizer.require(ctx, action, deal.tenant_id, deal.matter_id)
        return deal

    def _chunks_by_doc(
        self, tenant_id: str, matter_id: str
    ) -> dict[str, list[DocumentChunk]]:
        chunks = self.core_service.repository.list_chunks(tenant_id, matter_id)
        verify_retrieval_scope(chunks, tenant_id, matter_id)
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
