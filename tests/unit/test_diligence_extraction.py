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


def test_extract_from_sources_handles_public_document_financial_wording() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(),
                [
                    _chunk(
                        "FY26 revenue totalled £180 million. "
                        "FY26 reported EBITDA was £24m. "
                        "Management normalisation add-back of £5m was disclosed. "
                        "Seller response states recurring restructuring cost of £4 million."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Revenue"].value == "180"
    assert facts_by_label["Reported EBITDA"].value == "24"
    assert facts_by_label["EBITDA normalisation add-back"].value == "5"
    assert facts_by_label["Recurring restructuring cost"].value == "4"


def test_extract_from_sources_handles_public_report_metric_layout() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(),
                [
                    _chunk(
                        "The report shows FY25 revenue♦ £569.7m and adjusted "
                        "EBITDA £107.5m before operating segment analysis."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Revenue"].value == "569.7"
    assert facts_by_label["Revenue"].period == "FY25"
    assert facts_by_label["Reported EBITDA"].value == "107.5"
    assert facts_by_label["Revenue"].evidence[0].quote == (
        "The report shows FY25 revenue♦ £569.7m and adjusted EBITDA £107.5m before "
        "operating segment analysis."
    )
    assert facts_by_label["Reported EBITDA"].evidence[0].quote == (
        "The report shows FY25 revenue♦ £569.7m and adjusted EBITDA £107.5m before "
        "operating segment analysis."
    )


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


def test_extract_from_sources_handles_public_customer_concentration_wording() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.customer_data, workstream=Workstream.commercial),
                [
                    _chunk(
                        "Customer A accounted for 34% of total revenue. "
                        "Customer churn was 16% for the period."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Top customer revenue share"].value == "34"
    assert facts_by_label["Customer churn"].value == "16"


def test_extract_from_sources_handles_public_one_customer_note() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.customer_data, workstream=Workstream.commercial),
                [
                    _chunk(
                        "Revenues from one customer within the Business Transformation "
                        "segment represents approximately £75.9m (10%) of the Group's "
                        "total revenues."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Top customer revenue share"].value == "10"


def test_extract_from_sources_handles_public_material_customer_note() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.customer_data, workstream=Workstream.commercial),
                [
                    _chunk(
                        "Revenues from one customer represented approximately 68% "
                        "of water and wastewater revenues for the fiscal year."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Top customer revenue share"].value == "68"


def test_extract_from_sources_handles_public_customer_group_concentration_wording() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.customer_data, workstream=Workstream.commercial),
                [
                    _chunk(
                        "The top two named customers made up 39% of revenue. "
                        "Customer B comprised 16% of the same period revenue."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Top customer group revenue share"].value == "39"
    assert facts_by_label["Top customer revenue share"].value == "16"


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


def test_extract_from_sources_handles_public_contract_clause_wording() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "A change of control requires prior written consent before closing. "
                        "In addition, either party may terminate this Agreement for any "
                        "reason or no reason by giving the other party { 45 } days prior notice."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Change of control consent"].value == "required before assignment"
    assert facts_by_label["Termination for convenience"].value == "45 days notice"


def test_extract_from_sources_handles_word_and_number_notice_period() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "JPMC may terminate this Agreement for convenience, in whole "
                        "or in part, by giving Supplier at least thirty (30) days prior "
                        "written notice of the termination date."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Termination for convenience"].value == "30 days notice"


def test_extract_from_sources_handles_schedule_termination_for_convenience() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "JPMC may terminate this Agreement or any Schedule(s) for "
                        "convenience, in whole or in part, by giving Supplier at "
                        "least thirty (30) days prior written notice."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Termination for convenience"].value == "30 days notice"


def test_extract_from_sources_handles_public_operations_wording() -> None:
    facts, requests, responses = extract_from_sources(
        [
            (
                _source(
                    document_type=DocumentType.operational_report,
                    workstream=Workstream.operational,
                ),
                [
                    _chunk(
                        "Utilization was 72%. Backlog aged 19 days. "
                        "Regretted attrition reached 18% with 42 open vacancies. "
                        "Open item payroll schedule remains open and delayed 12 days. "
                        "Response does not provide supporting detail."
                    )
                ],
            )
        ]
    )

    facts_by_label = {fact.label: fact for fact in facts}
    assert facts_by_label["Utilisation"].value == "72"
    assert facts_by_label["SLA backlog"].value == "19"
    assert facts_by_label["Regretted attrition"].value == "18"
    assert facts_by_label["Open vacancies"].value == "42"
    assert requests[0].delayed_days == 12
    assert responses[0].topic == "Vendor response"


def test_extract_from_sources_skips_negated_contract_clauses() -> None:
    facts, _, _ = extract_from_sources(
        [
            (
                _source(document_type=DocumentType.contract, workstream=Workstream.commercial),
                [
                    _chunk(
                        "No change of control consent is required. "
                        "Change of control consent is not required. "
                        "Change of control consent shall not be required. "
                        "Change of control consent will not be required. "
                        "Change of control consent may not be required. "
                        "Change of control consent is not needed. "
                        "Change of control approval was not obtained. "
                        "Change of control does not require prior written approval. "
                        "No termination for convenience can be exercised on 30 days notice. "
                        "Supplier may not terminate this agreement for convenience on "
                        "30 days notice."
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
