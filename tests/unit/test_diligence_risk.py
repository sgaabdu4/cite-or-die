from cite_or_die.diligence.models import (
    Confidence,
    EvidenceLink,
    ExtractedFact,
    ExtractionField,
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


def test_long_termination_notice_does_not_create_short_notice_finding() -> None:
    long_notice = _termination_fact("180 days notice")
    short_notice = _termination_fact("30 days notice")

    long_findings = build_findings([long_notice], [])
    short_findings = build_findings([short_notice], [])

    assert "non_standard_clause" not in {finding.risk_code for finding in long_findings}
    assert "non_standard_clause" in {finding.risk_code for finding in short_findings}


def _fact(value: str, filename: str) -> ExtractedFact:
    return ExtractedFact(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        workstream=Workstream.commercial,
        field=ExtractionField.commercial_metric,
        label="Top customer revenue share",
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
