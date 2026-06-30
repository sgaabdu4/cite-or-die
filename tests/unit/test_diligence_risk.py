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
