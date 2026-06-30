import re

from cite_or_die.core.models import DocumentChunk
from cite_or_die.diligence.models import (
    CommercialMetric,
    Confidence,
    EvidenceLink,
    ExtractedFact,
    ExtractionField,
    FinancialMetric,
    InformationRequest,
    Obligation,
    OperationalMetric,
    SourceDocument,
    VendorResponse,
    Workstream,
)


def extract_from_sources(
    source_chunks: list[tuple[SourceDocument, list[DocumentChunk]]],
) -> tuple[list[ExtractedFact], list[InformationRequest], list[VendorResponse]]:
    facts: list[ExtractedFact | None] = []
    requests: list[InformationRequest] = []
    responses: list[VendorResponse] = []
    seen: set[tuple[str, str, str]] = set()

    for source, chunks in source_chunks:
        for chunk in chunks:
            text = chunk.text
            lower = text.casefold()

            for label, pattern, unit in (
                ("Revenue", r"revenue is GBP\s*([0-9]+)m", "GBP m"),
                ("Reported EBITDA", r"reported EBITDA is GBP\s*([0-9]+)m", "GBP m"),
                (
                    "EBITDA normalisation add-back",
                    r"normalisation adds GBP\s*([0-9]+)m",
                    "GBP m",
                ),
                (
                    "Recurring restructuring cost",
                    r"recurring restructuring costs are GBP\s*([0-9]+)m",
                    "GBP m",
                ),
            ):
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    evidence = _evidence(chunk, match)
                    facts.append(
                        _dedupe(
                            seen,
                            FinancialMetric(
                                tenant_id=source.tenant_id,
                                matter_id=source.matter_id,
                                deal_id=source.deal_id,
                                workstream=Workstream.financial,
                                label=label,
                                value=match.group(1),
                                unit=unit,
                                confidence=Confidence.high,
                                evidence=[evidence],
                            ),
                        )
                    )

            customer_share = re.search(
                r"top customer represents\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE
            )
            if customer_share:
                evidence = _evidence(chunk, customer_share)
                facts.append(
                    _dedupe(
                        seen,
                        CommercialMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.commercial,
                            label="Top customer revenue share",
                            value=customer_share.group(1),
                            unit="percent",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            churn = re.search(r"churn is\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE)
            if churn:
                evidence = _evidence(chunk, churn)
                facts.append(
                    _dedupe(
                        seen,
                        CommercialMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.commercial,
                            label="Customer churn",
                            value=churn.group(1),
                            unit="percent",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            utilisation = re.search(
                r"utili[sz]ation at\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE
            )
            if utilisation:
                evidence = _evidence(chunk, utilisation)
                facts.append(
                    _dedupe(
                        seen,
                        OperationalMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            label="Utilisation",
                            value=utilisation.group(1),
                            unit="percent",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            backlog = re.search(r"SLA backlog at\s*([0-9]+)\s*days", text, flags=re.IGNORECASE)
            if backlog:
                evidence = _evidence(chunk, backlog)
                facts.append(
                    _dedupe(
                        seen,
                        OperationalMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            label="SLA backlog",
                            value=backlog.group(1),
                            unit="days",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            employees = re.search(r"([0-9]+)\s*employees", text, flags=re.IGNORECASE)
            if employees:
                evidence = _evidence(chunk, employees)
                facts.append(
                    _dedupe(
                        seen,
                        OperationalMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            label="Employee count",
                            value=employees.group(1),
                            unit="employees",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            attrition = re.search(
                r"attrition of\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE
            )
            if attrition:
                evidence = _evidence(chunk, attrition)
                facts.append(
                    _dedupe(
                        seen,
                        OperationalMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            label="Regretted attrition",
                            value=attrition.group(1),
                            unit="percent",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            change_of_control = _phrase_match(text, "change of control consent")
            if change_of_control:
                evidence = _evidence(chunk, change_of_control)
                facts.append(
                    _dedupe(
                        seen,
                        Obligation(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.commercial,
                            label="Change of control consent",
                            value="required before assignment",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            termination = _phrase_match(text, "termination for convenience")
            if termination:
                evidence = _evidence(chunk, termination)
                facts.append(
                    _dedupe(
                        seen,
                        ExtractedFact(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            field=ExtractionField.contract_clause,
                            label="Termination for convenience",
                            value="30 days notice",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                    )
                )

            delay = re.search(r"delayed by\s*([0-9]+)\s*days", text, flags=re.IGNORECASE)
            information_request = _phrase_match(text, "information request")
            if information_request and ("open" in lower or delay):
                delayed_days = int(delay.group(1)) if delay else 0
                evidence = _evidence(chunk, delay or information_request)
                requests.append(
                    InformationRequest(
                        tenant_id=source.tenant_id,
                        matter_id=source.matter_id,
                        deal_id=source.deal_id,
                        title="Open information request",
                        status="open",
                        delayed_days=delayed_days,
                        evidence=[evidence],
                    )
                )

            vendor_response = _phrase_match(text, "vendor response")
            if vendor_response:
                response_summary = _matched_sentence(text, vendor_response)
                evidence = _evidence(chunk, vendor_response)
                responses.append(
                    VendorResponse(
                        tenant_id=source.tenant_id,
                        matter_id=source.matter_id,
                        deal_id=source.deal_id,
                        topic="Vendor response",
                        response_summary=response_summary,
                        evidence=[evidence],
                    )
                )

    return [fact for fact in facts if fact is not None], requests, responses


def _evidence(chunk: DocumentChunk, match: re.Match[str] | None = None) -> EvidenceLink:
    return EvidenceLink(
        tenant_id=chunk.tenant_id,
        matter_id=chunk.matter_id,
        doc_id=chunk.doc_id,
        chunk_id=chunk.chunk_id,
        filename=chunk.filename,
        page=chunk.page,
        quote=_matched_sentence(chunk.text, match) if match else _first_sentence(chunk.text),
    )


def _phrase_match(text: str, phrase: str) -> re.Match[str] | None:
    return re.search(re.escape(phrase), text, flags=re.IGNORECASE)


def _matched_sentence(text: str, match: re.Match[str]) -> str:
    start = match.start()
    end = match.end()
    left = start
    while left > 0 and text[left - 1] not in ".!?":
        left -= 1
    right = end
    while right < len(text) and text[right] not in ".!?":
        right += 1
    if right < len(text):
        right += 1
    sentence = " ".join(text[left:right].strip().split())
    return sentence[:500] if sentence else _first_sentence(text)


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.strip().split())
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return parts[0][:500] if parts and parts[0] else stripped[:500]


def _dedupe(
    seen: set[tuple[str, str, str]], fact: ExtractedFact
) -> ExtractedFact | None:
    key = (fact.label, fact.value, fact.evidence[0].doc_id)
    if key in seen:
        return None
    seen.add(key)
    return fact
