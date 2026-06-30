from cite_or_die.core.models import DocumentChunk
from cite_or_die.diligence.extraction import extract_from_sources
from cite_or_die.diligence.models import (
    Confidence,
    DocumentType,
    SourceDocument,
    Workstream,
)


def test_extract_from_sources_quotes_matching_sentence() -> None:
    source = _source()
    chunk = _chunk(
        "FY26 revenue is GBP 180m. "
        "Reported EBITDA is GBP 24m. "
        "Management normalisation adds GBP 5m for restructuring costs. "
        "Vendor response states recurring restructuring costs are GBP 4m."
    )

    facts, _, _ = extract_from_sources([(source, [chunk])])

    facts_by_label = {fact.label: fact for fact in facts}
    quotes_by_label = {fact.label: fact.evidence[0].quote for fact in facts}
    assert quotes_by_label["Revenue"] == "FY26 revenue is GBP 180m."
    assert facts_by_label["Revenue"].unit == "GBP m"
    assert facts_by_label["Revenue"].period == "FY26"
    assert (
        quotes_by_label["EBITDA normalisation add-back"]
        == "Management normalisation adds GBP 5m for restructuring costs."
    )
    assert (
        quotes_by_label["Recurring restructuring cost"]
        == "Vendor response states recurring restructuring costs are GBP 4m."
    )


def test_extract_from_sources_derives_financial_period_per_match() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(),
                [_chunk("FY25 revenue is GBP 120m. FY26 reported EBITDA is GBP 24m.")],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Revenue"].period == "FY25"
    assert facts_by_label["Reported EBITDA"].period == "FY26"


def test_extract_from_sources_emits_all_customer_share_matches() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.customer_data, workstream=Workstream.commercial),
                [
                    _chunk(
                        "Top customer represents 18 percent of revenue. "
                        "Top customer represents 42 percent of revenue."
                    )
                ],
            )
        ]
    )

    shares = [fact for fact in facts if fact.label == "Top customer revenue share"]
    assert [share.value for share in shares] == ["18", "42"]
    assert [share.evidence[0].quote for share in shares] == [
        "Top customer represents 18 percent of revenue.",
        "Top customer represents 42 percent of revenue.",
    ]


def test_extract_from_sources_ignores_non_recurring_restructuring_costs() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(),
                [
                    _chunk(
                        "Management normalisation adds GBP 5m. "
                        "Non-recurring restructuring costs are GBP 4m."
                    )
                ],
            )
        ]
    )

    labels = {fact.label for fact in facts}
    assert "EBITDA normalisation add-back" in labels
    assert "Recurring restructuring cost" not in labels


def test_extract_from_sources_parses_contract_clause_values() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "Change of control consent is required before assignment. "
                        "Termination for convenience can be exercised on 180 days notice."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Change of control consent"].value == "required before assignment"
    assert facts_by_label["Termination for convenience"].value == "180 days notice"


def test_extract_from_sources_skips_negated_contract_clauses() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "No change of control consent is required. "
                        "No termination for convenience can be exercised on 30 days notice."
                    )
                ],
            )
        ]
    )

    assert {fact.label for fact in facts} == set()


def _source(
    *,
    document_type: DocumentType = DocumentType.financials,
    workstream: Workstream = Workstream.financial,
) -> SourceDocument:
    return SourceDocument(
        tenant_id="tenant-a",
        matter_id="matter-a",
        deal_id="deal-a",
        doc_id="doc-a",
        filename="source.txt",
        content_type="text/plain",
        document_type=document_type,
        workstream=workstream,
        confidence=Confidence.high,
    )


def _chunk(text: str) -> DocumentChunk:
    return DocumentChunk(
        tenant_id="tenant-a",
        matter_id="matter-a",
        doc_id="doc-a",
        filename="source.txt",
        ordinal=0,
        text=text,
    )
