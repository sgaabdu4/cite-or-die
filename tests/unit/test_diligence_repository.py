import pytest

from cite_or_die.diligence.models import (
    Confidence,
    Deal,
    DiligenceKnowledgeBase,
    EvidenceLink,
    ExtractedFact,
    FinancialMetric,
    Finding,
    Materiality,
    ProviderAssistanceMetadata,
    ReportDraft,
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
    stored_fact = repository.list_facts("tenant-a", "matter-alpha", "deal-1")[0]
    assert isinstance(stored_fact, FinancialMetric)
    assert stored_fact.unit == "GBP m"
    assert stored_fact.period == "FY26"
    assert repository.list_findings("tenant-a", "matter-alpha", "deal-1") == [original_finding]
    assert repository.list_reports("tenant-a", "matter-alpha", "deal-1") == []


def test_replace_outputs_rejects_items_outside_target_scope(tmp_path) -> None:
    repository = DiligenceRepository(tmp_path / "state.sqlite")
    deal = Deal(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        name="Scoped Deal",
        target_business="Scoped Services",
        target_revenue_gbp_m=180,
        horizon_weeks=6,
    )
    foreign_fact = _fact(
        "42",
        "foreign-fact",
        tenant_id="tenant-b",
        matter_id="matter-beta",
        deal_id="deal-2",
    )

    with pytest.raises(ValueError, match="scope does not match"):
        repository.replace_outputs(
            knowledge_base=DiligenceKnowledgeBase(deal=deal, facts=[foreign_fact]),
            findings=[],
            insights=[],
            reports=[],
        )

    assert repository.list_facts("tenant-a", "matter-alpha", "deal-1") == []
    assert repository.list_facts("tenant-b", "matter-beta", "deal-2") == []


def test_replace_reports_preserves_provider_assistance_metadata(tmp_path) -> None:
    repository = DiligenceRepository(tmp_path / "state.sqlite")
    report = ReportDraft(
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
        title="AI-Assisted Risk Review",
        workstream=Workstream.cross_workstream,
        provider_assistance=ProviderAssistanceMetadata(
            model_provider="fake",
            model_version="fake-deterministic-v1",
            evidence_chunk_count=2,
        ),
    )

    repository.replace_reports(
        [report],
        tenant_id="tenant-a",
        matter_id="matter-alpha",
        deal_id="deal-1",
    )

    stored = repository.list_reports("tenant-a", "matter-alpha", "deal-1")
    assert stored == [report]
    assert stored[0].provider_assistance is not None
    assert stored[0].provider_assistance.model_provider == "fake"


def _fact(
    value: str,
    fact_id: str,
    *,
    tenant_id: str = "tenant-a",
    matter_id: str = "matter-alpha",
    deal_id: str = "deal-1",
) -> ExtractedFact:
    return FinancialMetric(
        fact_id=fact_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        deal_id=deal_id,
        workstream=Workstream.financial,
        label="EBITDA",
        value=value,
        period="FY26",
        unit="GBP m",
        confidence=Confidence.high,
        evidence=[_evidence(value, tenant_id=tenant_id, matter_id=matter_id)],
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


def _evidence(
    value: str,
    *,
    tenant_id: str = "tenant-a",
    matter_id: str = "matter-alpha",
) -> EvidenceLink:
    return EvidenceLink(
        tenant_id=tenant_id,
        matter_id=matter_id,
        doc_id=f"doc-{value}",
        chunk_id=f"chunk-{value}",
        filename=f"source-{value}.txt",
        quote=f"Reported EBITDA is GBP {value}m.",
    )
