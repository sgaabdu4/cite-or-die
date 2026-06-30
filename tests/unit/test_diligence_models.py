import pytest
from pydantic import ValidationError

from cite_or_die.diligence.models import (
    Confidence,
    EvidenceLink,
    Finding,
    Materiality,
    ReportClaim,
    ReportDraft,
    ReviewStatus,
    RiskSeverity,
    Workstream,
)


def test_finding_and_report_claims_require_traceable_evidence() -> None:
    evidence = EvidenceLink(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        doc_id="doc-1",
        chunk_id="chunk-1",
        filename="customer-contract.txt",
        quote="Change of control consent is required before assignment.",
    )

    finding = Finding(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        title="Change of control consent requirement",
        summary="A material customer contract requires consent before assignment.",
        risk_code="contract_consent",
        workstreams=[Workstream.commercial],
        severity=RiskSeverity.high,
        materiality=Materiality.material,
        confidence=Confidence.high,
        evidence=[evidence],
    )
    draft = ReportDraft(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        title="Executive Risk Summary",
        workstream=None,
        claims=[
            ReportClaim(
                text="A material customer contract requires consent before assignment.",
                evidence=[evidence],
            )
        ],
    )

    assert finding.evidence[0].quote.startswith("Change of control")
    assert draft.review_status is ReviewStatus.needs_review
    assert draft.claims[0].evidence[0].doc_id == "doc-1"

    with pytest.raises(ValidationError):
        Finding(
            tenant_id="tenant-a",
            matter_id="matter-alpha",
            deal_id="deal-1",
            title="Unsupported finding",
            summary="This finding has no traceable source.",
            risk_code="unsupported",
            workstreams=[Workstream.financial],
            severity=RiskSeverity.medium,
            materiality=Materiality.watchlist,
            confidence=Confidence.medium,
            evidence=[],
        )

    with pytest.raises(ValidationError):
        ReportClaim(text="Unsupported report claim.", evidence=[])
