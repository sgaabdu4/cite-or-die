from cite_or_die.core.models import Citation, Claim, DocumentChunk
from cite_or_die.diligence.models import (
    CrossWorkstreamInsight,
    Deal,
    DiligenceKnowledgeBase,
    EvidenceLink,
    Finding,
    ProviderAssistanceMetadata,
    ReportClaim,
    ReportDraft,
    ReviewStatus,
    Workstream,
)


def evidence_links_for_provider(
    knowledge_base: DiligenceKnowledgeBase,
    findings: list[Finding],
    insights: list[CrossWorkstreamInsight],
    reports: list[ReportDraft],
) -> list[EvidenceLink]:
    links: list[EvidenceLink] = []
    for fact in knowledge_base.facts:
        links.extend(fact.evidence)
    for request in knowledge_base.information_requests:
        links.extend(request.evidence)
    for response in knowledge_base.vendor_responses:
        links.extend(response.evidence)
    for finding in findings:
        links.extend(finding.evidence)
    for insight in insights:
        links.extend(insight.evidence)
    for report in reports:
        if report.provider_assistance is not None:
            continue
        for claim in report.claims:
            links.extend(claim.evidence)
    return _unique_evidence_links(links)


def provider_report_draft(
    deal: Deal,
    claims: list[Claim],
    *,
    model_provider: str,
    model_version: str,
    evidence_chunk_count: int,
) -> ReportDraft:
    return ReportDraft(
        tenant_id=deal.tenant_id,
        matter_id=deal.matter_id,
        deal_id=deal.deal_id,
        title="Provider-Assisted Risk Review",
        workstream=Workstream.cross_workstream,
        review_status=ReviewStatus.needs_review,
        provider_assistance=ProviderAssistanceMetadata(
            model_provider=model_provider,
            model_version=model_version,
            evidence_chunk_count=evidence_chunk_count,
        ),
        claims=[
            ReportClaim(
                text=claim.text,
                evidence=[
                    _evidence_from_citation(
                        citation,
                        source_field="provider_assisted_review",
                    )
                    for citation in claim.citations
                ],
            )
            for claim in claims
        ],
    )


def approx_token_count(question: str, chunks: list[DocumentChunk]) -> int:
    chunk_terms = sum(len(chunk.text.split()) for chunk in chunks)
    return max(1, len(question.split()) + chunk_terms)


def _unique_evidence_links(links: list[EvidenceLink]) -> list[EvidenceLink]:
    unique: list[EvidenceLink] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        key = (link.doc_id, link.chunk_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)
    return unique


def _evidence_from_citation(citation: Citation, *, source_field: str) -> EvidenceLink:
    return EvidenceLink(
        tenant_id=citation.tenant_id,
        matter_id=citation.matter_id,
        doc_id=citation.doc_id,
        chunk_id=citation.chunk_id,
        filename=citation.filename,
        quote=citation.quote,
        page=citation.page,
        source_field=source_field,
    )
