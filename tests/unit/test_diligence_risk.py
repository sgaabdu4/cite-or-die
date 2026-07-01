from cite_or_die.diligence.models import (
    Confidence,
    EvidenceLink,
    ExtractedFact,
    ExtractionField,
    FinancialMetric,
    Workstream,
)
from cite_or_die.diligence.risk import build_findings


def test_customer_concentration_uses_highest_material_share() -> None:
    low = _fact("18", "low-source.txt")
    high = _fact("42", "high-source.txt")

    findings = build_findings([low, high], [])

    concentration = next(
        finding for finding in findings if finding.risk_code == "customer_concentration"
    )
    assert concentration.evidence == high.evidence


def test_customer_group_concentration_creates_material_risk() -> None:
    group_share = _fact("39", "customer-source.txt", "Top customer group revenue share")

    findings = build_findings([group_share], [])

    concentration = next(
        finding for finding in findings if finding.risk_code == "customer_concentration"
    )
    assert concentration.title == "Top customer group concentration"
    assert concentration.owner == "commercial lead"
    assert concentration.evidence == group_share.evidence


def test_long_termination_notice_does_not_create_short_notice_finding() -> None:
    long_notice = _termination_fact("180 days notice")
    short_notice = _termination_fact("30 days notice")

    long_findings = build_findings([long_notice], [])
    short_findings = build_findings([short_notice], [])

    assert "non_standard_clause" not in {finding.risk_code for finding in long_findings}
    assert "non_standard_clause" in {finding.risk_code for finding in short_findings}


def test_earnings_normalisation_requires_matching_or_unknown_period() -> None:
    fy25_addback = _financial_fact("EBITDA normalisation add-back", "5", "FY25")
    fy26_recurring = _financial_fact("Recurring restructuring cost", "4", "FY26")
    unknown_recurring = _financial_fact("Recurring restructuring cost", "3", None)

    mismatched_findings = build_findings([fy25_addback, fy26_recurring], [])
    unknown_findings = build_findings([fy25_addback, unknown_recurring], [])

    assert "earnings_normalisation" not in {
        finding.risk_code for finding in mismatched_findings
    }
    assert "earnings_normalisation" in {finding.risk_code for finding in unknown_findings}


def _fact(
    value: str, filename: str, label: str = "Top customer revenue share"
) -> ExtractedFact:
    return ExtractedFact(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        workstream=Workstream.commercial,
        field=ExtractionField.commercial_metric,
        label=label,
        value=value,
        confidence=Confidence.high,
        evidence=[
            EvidenceLink(
                tenant_id="tenant-a",
                matter_id="matter-alpha",
                doc_id=f"doc-{value}",
                chunk_id=f"chunk-{value}",
                filename=filename,
                quote=f"Top customer represents {value} percent of revenue.",
            )
        ],
    )


def _financial_fact(label: str, value: str, period: str | None) -> FinancialMetric:
    return FinancialMetric(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        workstream=Workstream.financial,
        label=label,
        value=value,
        period=period,
        unit="GBP m",
        confidence=Confidence.high,
        evidence=[
            EvidenceLink(
                tenant_id="tenant-a",
                matter_id="matter-alpha",
                doc_id=f"doc-{label}-{period}",
                chunk_id=f"chunk-{label}-{period}",
                filename="financials.txt",
                quote=f"{label} is GBP {value}m for {period or 'unknown period'}.",
            )
        ],
    )


def _termination_fact(value: str) -> ExtractedFact:
    return ExtractedFact(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        workstream=Workstream.operational,
        field=ExtractionField.contract_clause,
        label="Termination for convenience",
        value=value,
        confidence=Confidence.high,
        evidence=[
            EvidenceLink(
                tenant_id="tenant-a",
                matter_id="matter-alpha",
                doc_id="doc-contract",
                chunk_id="chunk-contract",
                filename="contract.txt",
                quote=f"Termination for convenience can be exercised on {value}.",
            )
        ],
    )
