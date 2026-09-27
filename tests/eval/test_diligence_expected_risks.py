import pytest

from cite_or_die.core.models import AuthContext, Role
from cite_or_die.core.service import CiteOrDieService
from cite_or_die.diligence.models import RiskSeverity
from cite_or_die.diligence.service import DiligenceService


@pytest.mark.asyncio()
async def test_synthetic_deal_room_surfaces_expected_material_risks(settings) -> None:
    core = CiteOrDieService(settings)
    diligence = DiligenceService(settings, core_service=core)
    ctx = AuthContext(tenant_id="eval", matter_id="live-cycle", subject="eval", roles=[Role.admin])
    await core.upload(
        ctx,
        "customer-data.txt",
        "text/plain",
        (
            b"Top customer represents 36 percent of revenue. "
            b"Customer churn is 17 percent and renewal status is incomplete."
        ),
    )
    await core.upload(
        ctx,
        "financials-and-responses.txt",
        "text/plain",
        (
            b"FY26 revenue is GBP 205m. Reported EBITDA is GBP 28m. "
            b"Management normalisation adds GBP 6m for restructuring costs. "
            b"Vendor response states recurring restructuring costs are GBP 5m."
        ),
    )
    await core.upload(
        ctx,
        "contract-and-ir.txt",
        "text/plain",
        (
            b"Change of control consent is required before assignment. "
            b"Information request payroll detail remains open and delayed by 10 days."
        ),
    )
    deal = diligence.create_deal(
        ctx,
        name="Evaluation Deal",
        target_business="Evaluation Services",
        target_revenue_gbp_m=205,
        horizon_weeks=5,
    )

    result = diligence.run_acceleration(ctx, deal.deal_id)

    by_code = {finding.risk_code: finding for finding in result.findings}
    assert {
        "customer_concentration",
        "earnings_normalisation",
        "contract_consent",
        "open_information_request",
    } <= set(by_code)
    assert by_code["customer_concentration"].severity is RiskSeverity.high
    assert by_code["earnings_normalisation"].evidence
    assert all(finding.evidence for finding in result.findings)
