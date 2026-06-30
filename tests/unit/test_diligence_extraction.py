from cite_or_die.core.models import DocumentChunk
from cite_or_die.diligence.extraction import extract_from_sources
from cite_or_die.diligence.models import (
    Confidence,
    DocumentType,
    SourceDocument,
    Workstream,
)


def test_extract_from_sources_quotes_matching_sentence() -> None:
    source = SourceDocument(
        tenant_id="tenant-a",
        matter_id="matter-a",
        deal_id="deal-a",
        doc_id="doc-a",
        filename="financials.txt",
        content_type="text/plain",
        document_type=DocumentType.financials,
        workstream=Workstream.financial,
        confidence=Confidence.high,
    )
    chunk = DocumentChunk(
        tenant_id="tenant-a",
        matter_id="matter-a",
        doc_id="doc-a",
        filename="financials.txt",
        ordinal=0,
        text=(
            "FY26 revenue is GBP 180m. "
            "Reported EBITDA is GBP 24m. "
            "Management normalisation adds GBP 5m for restructuring costs. "
            "Vendor response states recurring restructuring costs are GBP 4m."
        ),
    )

    facts, _, _ = extract_from_sources([(source, [chunk])])

    quotes_by_label = {fact.label: fact.evidence[0].quote for fact in facts}
    assert quotes_by_label["Revenue"] == "FY26 revenue is GBP 180m."
    assert (
        quotes_by_label["EBITDA normalisation add-back"]
        == "Management normalisation adds GBP 5m for restructuring costs."
    )
    assert (
        quotes_by_label["Recurring restructuring cost"]
        == "Vendor response states recurring restructuring costs are GBP 4m."
    )
