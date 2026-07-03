from cite_or_die.diligence.classification import classify_source
from cite_or_die.diligence.models import DocumentType, Workstream


def test_classifies_messy_source_names_by_content_and_workstream() -> None:
    customer = classify_source(
        filename="2026_Q2_TOP_CUST_rev_export_FINAL.xlsx",
        content_type="text/csv",
        sample_text="Top customer revenue, churn, renewal status and customer concentration.",
    )
    contract = classify_source(
        filename="folder-17--msa-signed-scan.pdf",
        content_type="application/pdf",
        sample_text="Master services agreement with change of control consent and termination.",
    )
    qa_log = classify_source(
        filename="responses v3 no clean headers.csv",
        content_type="text/csv",
        sample_text="Question owner status response due date open delayed vendor response.",
    )

    assert customer.document_type is DocumentType.customer_data
    assert customer.workstream is Workstream.commercial
    assert customer.confidence.value >= 0.75

    assert contract.document_type is DocumentType.contract
    assert contract.workstream is Workstream.operational
    assert contract.confidence.value >= 0.75

    assert qa_log.document_type is DocumentType.qa_log
    assert qa_log.workstream is Workstream.operational
    assert qa_log.confidence.value >= 0.6


def test_short_classification_terms_require_token_boundaries() -> None:
    classification = classify_source(
        filename="threshold-claims-analysis-translations.txt",
        content_type="text/plain",
        sample_text=(
            "Three phrases describe thresholds, claimsanalysis, and translations "
            "without standalone source-type acronyms."
        ),
    )
    contract = classify_source(
        filename="signed-msa.pdf",
        content_type="application/pdf",
        sample_text="Document list entry without other contract wording.",
    )

    assert classification.document_type is DocumentType.unknown
    assert contract.document_type is DocumentType.contract


def test_filename_source_type_hint_wins_over_overlapping_content() -> None:
    management = classify_source(
        filename="00-management-presentation-public-context.txt",
        content_type="text/plain",
        sample_text=(
            "FY24 revenue is GBP 192m. Reported EBITDA is GBP 22.8m. "
            "The strategy section describes market overview and customer concentration."
        ),
    )
    vendor = classify_source(
        filename="07-vendor-response-financial-normalisation.txt",
        content_type="text/plain",
        sample_text=(
            "Vendor response states recurring restructuring costs are GBP 5m. "
            "The finance owner response is still pending."
        ),
    )
    benchmark = classify_source(
        filename="09-sector-benchmark-public-market-information.txt",
        content_type="text/plain",
        sample_text=(
            "Sector benchmark and market data describe customer concentration, "
            "pipeline pressure, public market information, and listed peer performance."
        ),
    )

    assert management.document_type is DocumentType.management_presentation
    assert management.workstream is Workstream.commercial
    assert vendor.document_type is DocumentType.vendor_response
    assert vendor.workstream is Workstream.financial
    assert benchmark.document_type is DocumentType.sector_benchmark
    assert benchmark.workstream is Workstream.commercial
