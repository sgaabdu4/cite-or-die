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
