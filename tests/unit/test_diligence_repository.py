import pytest

from cite_or_die.diligence.models import (
    Confidence,
    Deal,
    DiligenceKnowledgeBase,
    EvidenceLink,
    ExtractedFact,
    ExtractionField,
    Finding,
    Materiality,
    RiskSeverity,
    Workstream,
)
from cite_or_die.diligence.repository import DiligenceRepository


def test_replace_outputs_rolls_back_all_tables_on_failure(tmp_path) -> None:
    repository = DiligenceRepository(tmp_path / "state.sqlite")
    deal = Deal(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        name="Atomic Deal",
        target_business="Atomic Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
    )
    original_fact = _fact("24", "original-fact")
    original_finding = _finding("original-risk", original_fact.evidence)
    replacement_fact = _fact("42", "replacement-fact")
    replacement_finding = _finding("replacement-risk", replacement_fact.evidence)
    repository.replace_outputs(
        knowledge_base=DiligenceKnowledgeBase(deal=deal, facts=[original_fact]),
        findings=[original_finding],
        insights=[],
        reports=[],
    )

    with pytest.raises(AttributeError):
        repository.replace_outputs(
            knowledge_base=DiligenceKnowledgeBase(deal=deal, facts=[replacement_fact]),
            findings=[replacement_finding],
            insights=[],
            reports=[object()],  # type: ignore[list-item]
        )

    assert repository.list_facts("tenant-a", "matter-alpha", "deal-1") == [original_fact]
    assert repository.list_findings("tenant-a", "matter-alpha", "deal-1") == [
        original_finding
    ]
    assert repository.list_reports("tenant-a", "matter-alpha", "deal-1") == []


def _fact(value: str, fact_id: str) -> ExtractedFact:
    return ExtractedFact(
        fact_id=fact_id,
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        workstream=Workstream.financial,
        field=ExtractionField.financial_metric,
        label="EBITDA",
        value=value,
        confidence=Confidence.high,
        evidence=[_evidence(value)],
    )


def _finding(risk_code: str, evidence: list[EvidenceLink]) -> Finding:
    return Finding(
        finding_id=f"{risk_code}-id",
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        title=risk_code,
        summary=risk_code,
        risk_code=risk_code,
        workstreams=[Workstream.financial],
        severity=RiskSeverity.medium,
        materiality=Materiality.watchlist,
        confidence=Confidence.high,
        evidence=evidence,
    )


def _evidence(value: str) -> EvidenceLink:
    return EvidenceLink(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        doc_id=f"doc-{value}",
        chunk_id=f"chunk-{value}",
        filename=f"source-{value}.txt",
        quote=f"Reported EBITDA is GBP {value}m.",
    )
