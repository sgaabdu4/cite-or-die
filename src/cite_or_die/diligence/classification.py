import re

from cite_or_die.diligence.models import (
    Confidence,
    DocumentType,
    SourceClassification,
    Workstream,
)

_RULES: tuple[tuple[DocumentType, Workstream, tuple[str, ...]], ...] = (
    (
        DocumentType.contract,
        Workstream.operational,
        ("contract", "agreement", "msa", "assignment", "termination", "change of control"),
    ),
    (
        DocumentType.financials,
        Workstream.financial,
        ("financial", "ebitda", "revenue", "normalisation", "gross margin", "cash flow"),
    ),
    (
        DocumentType.customer_data,
        Workstream.commercial,
        ("customer", "churn", "renewal", "concentration", "top customer", "account revenue"),
    ),
    (
        DocumentType.hr_record,
        Workstream.operational,
        ("hr", "employee", "employees", "attrition", "vacancies", "payroll"),
    ),
    (
        DocumentType.operational_report,
        Workstream.operational,
        ("operational", "operations", "utilisation", "utilization", "sla", "backlog"),
    ),
    (
        DocumentType.org_chart,
        Workstream.operational,
        ("org chart", "organisation", "organization", "reporting line", "leadership"),
    ),
    (
        DocumentType.management_presentation,
        Workstream.commercial,
        ("management deck", "management presentation", "market overview", "strategy"),
    ),
    (
        DocumentType.qa_log,
        Workstream.operational,
        ("q&a", "qa log", "question", "response", "owner", "status", "due date"),
    ),
    (
        DocumentType.information_request,
        Workstream.operational,
        ("information request", "request list", "ir list", "open item", "delayed"),
    ),
    (
        DocumentType.vendor_response,
        Workstream.financial,
        ("vendor response", "seller response", "response states", "supporting detail"),
    ),
    (
        DocumentType.prior_deal_precedent,
        Workstream.financial,
        ("prior deal", "precedent", "deal precedent"),
    ),
    (
        DocumentType.comparable_transaction,
        Workstream.financial,
        ("comparable transaction", "comps", "transaction multiple"),
    ),
    (
        DocumentType.sector_benchmark,
        Workstream.commercial,
        ("sector benchmark", "benchmark", "market data"),
    ),
    (
        DocumentType.public_market_information,
        Workstream.financial,
        ("public market", "listed peer", "market information"),
    ),
)


def classify_source(
    *, filename: str, content_type: str, sample_text: str = ""
) -> SourceClassification:
    text = _normalise(f"{filename} {content_type} {sample_text}")
    filename_text = _normalise(filename)
    if "qa log" in filename_text or "q&a" in filename_text:
        return SourceClassification(
            document_type=DocumentType.qa_log,
            workstream=Workstream.operational,
            confidence=Confidence.high,
            matched_terms=["qa log"],
        )
    best: tuple[DocumentType, Workstream, list[str]] | None = None
    for document_type, workstream, terms in _RULES:
        matched = [term for term in terms if _contains_term(text, term)]
        if matched and (best is None or len(matched) > len(best[2])):
            best = (document_type, workstream, matched)

    if best is None:
        return SourceClassification(
            document_type=DocumentType.unknown,
            workstream=Workstream.operational,
            confidence=Confidence.low,
            matched_terms=[],
        )

    document_type, workstream, matched_terms = best
    confidence = Confidence.high if len(matched_terms) >= 2 else Confidence.medium
    return SourceClassification(
        document_type=document_type,
        workstream=workstream,
        confidence=confidence,
        matched_terms=matched_terms,
    )


def _normalise(value: str) -> str:
    return re.sub(r"[_\-/]+", " ", value.casefold())


def _contains_term(text: str, term: str) -> bool:
    normalised = _normalise(term)
    return normalised in text
