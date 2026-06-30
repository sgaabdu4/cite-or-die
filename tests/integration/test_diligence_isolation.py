import pytest
from fastapi import HTTPException

from cite_or_die.core.models import AuthContext, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.diligence.service import DiligenceService


@pytest.mark.asyncio()
async def test_diligence_objects_remain_tenant_and_matter_scoped(settings) -> None:
    core = CiteOrDieService(settings)
    diligence = DiligenceService(settings, core_service=core)
    alpha = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="analyst-a", roles=[Role.admin]
    )
    beta = AuthContext(
        tenant_id="tenant-b", matter_id="matter-beta", subject="analyst-b", roles=[Role.admin]
    )
    await core.upload(
        alpha,
        "alpha-financials.txt",
        "text/plain",
        b"FY26 revenue is GBP 180m. Reported EBITDA is GBP 24m.",
    )
    await core.upload(
        beta,
        "beta-financials.txt",
        "text/plain",
        b"FY26 revenue is GBP 110m. Reported EBITDA is GBP 9m.",
    )

    deal = diligence.create_deal(
        alpha,
        name="Alpha acquisition",
        target_business="Alpha Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
    )
    diligence.classify_sources(alpha, deal.deal_id)
    result = diligence.run_acceleration(alpha, deal.deal_id)

    assert result.deal.tenant_id == "tenant-a"
    assert all(source.tenant_id == "tenant-a" for source in result.knowledge_base.sources)
    assert all(source.matter_id == "matter-alpha" for source in result.knowledge_base.sources)

    with pytest.raises(HTTPException):
        diligence.list_findings(beta, deal.deal_id)


@pytest.mark.asyncio()
async def test_diligence_audit_events_do_not_store_raw_source_text(settings) -> None:
    core = CiteOrDieService(settings)
    diligence = DiligenceService(settings, core_service=core)
    ctx = AuthContext(
        tenant_id="tenant-a", matter_id="matter-alpha", subject="analyst-a", roles=[Role.admin]
    )
    raw_source_text = (
        b"Top customer represents 35 percent of revenue. "
        b"Management normalisation adds GBP 5m for restructuring costs. "
        b"Vendor response states recurring restructuring costs are GBP 4m."
    )
    await core.upload(ctx, "raw-source.txt", "text/plain", raw_source_text)
    deal = diligence.create_deal(
        ctx,
        name="Audit Scope Deal",
        target_business="Audit Scope Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
    )

    diligence.run_acceleration(ctx, deal.deal_id)

    audit_rows = core.audit.recent(limit=10)
    diligence_rows = [row for row in audit_rows if row["event_type"] == "diligence"]
    serialized = "\n".join(row["payload_json"] for row in diligence_rows)
    assert diligence_rows
    assert deal.deal_id in serialized
    assert "finding_count" in serialized
    assert "Top customer represents" not in serialized
    assert "Vendor response states" not in serialized
