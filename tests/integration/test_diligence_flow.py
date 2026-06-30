import pytest

from cite_or_die.core.models import AuthContext, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.diligence.models import (
    DocumentType,
    ReviewStatus,
    Workstream,
)
from cite_or_die.diligence.service import DiligenceService


@pytest.mark.asyncio()
async def test_diligence_pipeline_builds_evidence_backed_outputs(settings) -> None:
    core = CiteOrDieService(settings)
    diligence = DiligenceService(settings, core_service=core)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="analyst-a", roles=[Role.admin]
    )
    await _upload_synthetic_deal_room(core, ctx)

    deal = diligence.create_deal(
        ctx,
        name="Project Northstar",
        target_business="Northstar Managed Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
    )
    sources = diligence.classify_sources(ctx, deal.deal_id)
    result = diligence.run_acceleration(ctx, deal.deal_id)

    assert {source.document_type for source in sources} >= {
        DocumentType.contract,
        DocumentType.financials,
        DocumentType.customer_data,
        DocumentType.operational_report,
        DocumentType.hr_record,
        DocumentType.qa_log,
    }
    assert {source.workstream for source in sources} >= {
        Workstream.commercial,
        Workstream.operational,
        Workstream.financial,
    }
    assert result.knowledge_base.facts
    assert result.findings
    assert result.insights
    assert result.report_drafts

    finding_codes = {finding.risk_code for finding in result.findings}
    assert "customer_concentration" in finding_codes
    assert "earnings_normalisation" in finding_codes
    assert "open_information_request" in finding_codes
    assert "contract_consent" in finding_codes

    chunk_ids = {
        (chunk.doc_id, chunk.chunk_id)
        for chunk in core.repository.list_chunks(ctx.tenant_id, ctx.matter_id)
    }
    for fact in result.knowledge_base.facts:
        _assert_evidence_verified(fact.evidence, chunk_ids, ctx)
    for finding in result.findings:
        _assert_evidence_verified(finding.evidence, chunk_ids, ctx)
    for insight in result.insights:
        _assert_evidence_verified(insight.evidence, chunk_ids, ctx)
    for draft in result.report_drafts:
        assert draft.review_status is ReviewStatus.needs_review
        for claim in draft.claims:
            _assert_evidence_verified(claim.evidence, chunk_ids, ctx)


@pytest.mark.asyncio()
async def test_diligence_deal_uses_explicit_source_document_scope(settings) -> None:
    core = CiteOrDieService(settings)
    diligence = DiligenceService(settings, core_service=core)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="analyst-a", roles=[Role.admin]
    )
    excluded = await core.upload(
        ctx,
        "legacy-customer-pack.txt",
        "text/plain",
        b"Top customer represents 90 percent of revenue.",
    )
    included = await core.upload(
        ctx,
        "selected-financial-pack.txt",
        "text/plain",
        b"FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m.",
    )

    deal = diligence.create_deal(
        ctx,
        name="Scoped Deal",
        target_business="Scoped Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
        source_doc_ids=[included.document.doc_id],
    )
    sources = diligence.classify_sources(ctx, deal.deal_id)
    result = diligence.run_acceleration(ctx, deal.deal_id)

    assert {source.doc_id for source in sources} == {included.document.doc_id}
    evidence_doc_ids = {
        link.doc_id
        for fact in result.knowledge_base.facts
        for link in fact.evidence
    }
    assert excluded.document.doc_id not in evidence_doc_ids
    assert evidence_doc_ids == {included.document.doc_id}


def _assert_evidence_verified(evidence, chunk_ids, ctx: AuthContext) -> None:
    assert evidence
    for link in evidence:
        assert link.tenant_id == ctx.tenant_id
        assert link.matter_id == ctx.matter_id
        assert (link.doc_id, link.chunk_id) in chunk_ids
        assert link.quote.strip()


async def _upload_synthetic_deal_room(
    core: CiteOrDieService, ctx: AuthContext
) -> None:
    uploads = {
        "01-customer-contract-scan.txt": (
            "Master services agreement for Northstar Managed Services. "
            "Change of control consent is required before assignment. "
            "Termination for convenience can be exercised on 30 days notice."
        ),
        "02-financial-pack-fy26.txt": (
            "FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m. "
            "Management normalisation adds GBP 5m for restructuring costs. "
            "Vendor response states recurring restructuring costs are GBP 4m."
        ),
        "03-operations-report.txt": (
            "Operational report shows utilisation at 72 percent and SLA backlog at 19 days. "
            "Three offshore delivery leads own transition-critical workflows."
        ),
        "04-customer-data-export.txt": (
            "Top customer represents 34 percent of revenue. "
            "Customer churn is 16 percent and renewal status is incomplete for two key accounts."
        ),
        "05-hr-records.txt": (
            "HR records show 940 employees, regretted attrition of 18 percent, "
            "and 42 open vacancies in delivery roles."
        ),
        "06-qa-log-and-ir-list.txt": (
            "Information request HR attrition schedule remains open and delayed by 12 days. "
            "Vendor response does not provide supporting payroll detail."
        ),
    }
    for filename, text in uploads.items():
        await core.upload(ctx, filename, "text/plain", text.encode("utf-8"))
