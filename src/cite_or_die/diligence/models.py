from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, SerializeAsAny, field_validator, model_validator

from cite_or_die.core.models import GuardrailDecision


class Workstream(str, Enum):
    commercial = "commercial"
    operational = "operational"
    financial = "financial"
    cross_workstream = "cross_workstream"


class DocumentType(str, Enum):
    contract = "contract"
    financials = "financials"
    org_chart = "org_chart"
    operational_report = "operational_report"
    customer_data = "customer_data"
    hr_record = "hr_record"
    management_presentation = "management_presentation"
    qa_log = "qa_log"
    information_request = "information_request"
    vendor_response = "vendor_response"
    prior_deal_precedent = "prior_deal_precedent"
    comparable_transaction = "comparable_transaction"
    sector_benchmark = "sector_benchmark"
    public_market_information = "public_market_information"
    unknown = "unknown"


class ExtractionField(str, Enum):
    contract_clause = "contract_clause"
    obligation = "obligation"
    date_term = "date_term"
    financial_metric = "financial_metric"
    operational_metric = "operational_metric"
    commercial_metric = "commercial_metric"
    information_request = "information_request"
    vendor_response = "vendor_response"


class RiskSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Materiality(str, Enum):
    immaterial = "immaterial"
    watchlist = "watchlist"
    material = "material"
    critical = "critical"


class Confidence(float, Enum):
    low = 0.45
    medium = 0.65
    high = 0.85


class ReviewStatus(str, Enum):
    needs_review = "needs_review"
    in_review = "in_review"
    approved = "approved"
    escalated = "escalated"
    rejected = "rejected"


class Escalation(str, Enum):
    none = "none"
    workstream_lead = "workstream_lead"
    deal_lead = "deal_lead"
    client = "client"


class EvidenceLink(BaseModel):
    tenant_id: str
    matter_id: str
    doc_id: str
    chunk_id: str
    filename: str
    quote: str
    page: int | None = None
    source_field: str | None = None

    @field_validator("quote")
    @classmethod
    def quote_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence quote must not be empty")
        return value.strip()


class Deal(BaseModel):
    deal_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    name: str
    target_business: str
    target_revenue_gbp_m: int
    horizon_weeks: int = Field(ge=4, le=8)
    source_doc_ids: list[str] = Field(default_factory=list, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SourceClassification(BaseModel):
    document_type: DocumentType
    workstream: Workstream
    confidence: Confidence
    matched_terms: list[str] = Field(default_factory=list)


class SourceDocument(BaseModel):
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    doc_id: str
    filename: str
    content_type: str
    document_type: DocumentType
    workstream: Workstream
    confidence: Confidence
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExtractedFact(BaseModel):
    fact_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    workstream: Workstream
    field: ExtractionField
    label: str
    value: str
    confidence: Confidence = Confidence.medium
    evidence: list[EvidenceLink] = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Obligation(ExtractedFact):
    field: ExtractionField = ExtractionField.obligation
    owner: str | None = None
    due_date: str | None = None


class DateTerm(ExtractedFact):
    field: ExtractionField = ExtractionField.date_term
    normalised_date: str | None = None


class FinancialMetric(ExtractedFact):
    field: ExtractionField = ExtractionField.financial_metric
    period: str | None = None
    unit: str | None = None


class OperationalMetric(ExtractedFact):
    field: ExtractionField = ExtractionField.operational_metric
    period: str | None = None
    unit: str | None = None


class CommercialMetric(ExtractedFact):
    field: ExtractionField = ExtractionField.commercial_metric
    period: str | None = None
    unit: str | None = None


class InformationRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    title: str
    owner: str | None = None
    status: str = "open"
    delayed_days: int = 0
    evidence: list[EvidenceLink] = Field(min_length=1)


class VendorResponse(BaseModel):
    response_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    topic: str
    response_summary: str
    evidence: list[EvidenceLink] = Field(min_length=1)


class Finding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    title: str
    summary: str
    risk_code: str
    workstreams: list[Workstream] = Field(min_length=1)
    severity: RiskSeverity
    materiality: Materiality
    confidence: Confidence
    evidence: list[EvidenceLink] = Field(min_length=1)
    owner: str | None = None
    status: ReviewStatus = ReviewStatus.needs_review
    escalation: Escalation = Escalation.none
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CrossWorkstreamInsight(BaseModel):
    insight_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    title: str
    summary: str
    workstreams: list[Workstream] = Field(min_length=2)
    confidence: Confidence
    evidence: list[EvidenceLink] = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.needs_review
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_distinct_workstreams(self) -> "CrossWorkstreamInsight":
        if len(set(self.workstreams)) < 2:
            raise ValueError("insight must span at least two workstreams")
        return self


class ReportClaim(BaseModel):
    text: str
    evidence: list[EvidenceLink] = Field(min_length=1)


class ProviderAssistanceMetadata(BaseModel):
    model_provider: str
    model_version: str
    evidence_chunk_count: int = Field(ge=1)


class ReportDraft(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id: str
    matter_id: str
    deal_id: str
    title: str
    workstream: Workstream | None
    claims: list[ReportClaim] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.needs_review
    provider_assistance: ProviderAssistanceMetadata | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DiligenceKnowledgeBase(BaseModel):
    deal: Deal
    sources: list[SourceDocument] = Field(default_factory=list)
    facts: list[SerializeAsAny[ExtractedFact]] = Field(default_factory=list)
    information_requests: list[InformationRequest] = Field(default_factory=list)
    vendor_responses: list[VendorResponse] = Field(default_factory=list)


class DiligenceRunResult(BaseModel):
    deal: Deal
    knowledge_base: DiligenceKnowledgeBase
    findings: list[Finding] = Field(default_factory=list)
    insights: list[CrossWorkstreamInsight] = Field(default_factory=list)
    report_drafts: list[ReportDraft] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class ProviderAssistedDiligenceResult(BaseModel):
    deal: Deal
    report_draft: ReportDraft
    guardrails: list[GuardrailDecision] = Field(default_factory=list)
    model_provider: str
    model_version: str
    evidence_chunk_count: int = Field(ge=1)
