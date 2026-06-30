import re
from collections.abc import Iterator

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

_DedupeKey = tuple[str, str, str, str, int, int, str | None]


def extract_from_sources(
    source_chunks: list[tuple[SourceDocument, list[DocumentChunk]]],
) -> tuple[list[ExtractedFact], list[InformationRequest], list[VendorResponse]]:
    facts: list[ExtractedFact | None] = []
    requests: list[InformationRequest] = []
    responses: list[VendorResponse] = []
    seen: set[_DedupeKey] = set()

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
                for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                    if label == "Recurring restructuring cost" and _is_negated_match(
                        text, match, "recurring restructuring costs"
                    ):
                        continue
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
                                period=_period_for_match(text, match),
                                unit=unit,
                                confidence=Confidence.high,
                                evidence=[evidence],
                            ),
                            match,
                        )
                    )

            for customer_share in re.finditer(
                r"top customer represents\s*([0-9]+)\s*percent",
                text,
                flags=re.IGNORECASE,
            ):
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
                        customer_share,
                    )
                )

            for churn in re.finditer(r"churn is\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE):
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
                        churn,
                    )
                )

            for utilisation in re.finditer(
                r"utili[sz]ation at\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE
            ):
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
                        utilisation,
                    )
                )

            for backlog in re.finditer(
                r"SLA backlog at\s*([0-9]+)\s*days", text, flags=re.IGNORECASE
            ):
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
                        backlog,
                    )
                )

            for employees in re.finditer(r"([0-9]+)\s*employees", text, flags=re.IGNORECASE):
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
                        employees,
                    )
                )

            for attrition in re.finditer(
                r"attrition of\s*([0-9]+)\s*percent", text, flags=re.IGNORECASE
            ):
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
                        attrition,
                    )
                )

            for change_of_control in _required_consent_matches(text):
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
                        change_of_control,
                    )
                )

            for termination in _termination_notice_matches(text):
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
                            value=f"{termination.group(1)} days notice",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                        termination,
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
    return next(_phrase_matches(text, phrase), None)


def _phrase_matches(text: str, phrase: str) -> Iterator[re.Match[str]]:
    yield from re.finditer(re.escape(phrase), text, flags=re.IGNORECASE)


def _required_consent_matches(text: str) -> Iterator[re.Match[str]]:
    for match in _phrase_matches(text, "change of control consent"):
        sentence = _matched_sentence(text, match)
        if _is_negated_phrase(sentence, "change of control consent"):
            continue
        if re.search(
            r"\b(requires?|required|needed)\b|\bmust\s+be\s+(obtained|secured)\b",
            sentence,
            flags=re.IGNORECASE,
        ):
            yield match


def _termination_notice_matches(text: str) -> Iterator[re.Match[str]]:
    pattern = r"termination for convenience[^.!?]{0,200}?\b([0-9]+)\s*-?\s*days?\s+notice\b"
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        sentence = _matched_sentence(text, match)
        if not _is_negated_phrase(sentence, "termination for convenience"):
            yield match


def _is_negated_match(text: str, match: re.Match[str], phrase: str) -> bool:
    return _is_negated_phrase(_matched_sentence(text, match), phrase)


def _is_negated_phrase(sentence: str, phrase: str) -> bool:
    phrase_pattern = r"\s+".join(re.escape(part) for part in phrase.casefold().split())
    lower = sentence.casefold()
    return bool(
        re.search(rf"\b(?:no|not|without)\s+{phrase_pattern}\b", lower)
        or re.search(rf"\bnon[-\s]*{phrase_pattern}\b", lower)
        or re.search(rf"\b{phrase_pattern}\b\s+(?:is|are|was|were)\s+not\b", lower)
        or re.search(rf"\b{phrase_pattern}\b\s+(?:cannot|can't)\b", lower)
    )


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


def _period_for_match(text: str, match: re.Match[str]) -> str | None:
    left = max(0, match.start() - 160)
    right = min(len(text), match.end() + 160)
    window = text[left:right]
    match_start = match.start() - left
    match_end = match.end() - left
    period_matches = list(_period_matches(window))
    if not period_matches:
        return None
    nearest = min(
        period_matches,
        key=lambda period_match: _period_distance(period_match, match_start, match_end),
    )
    return nearest.group(1).upper()


def _period_matches(text: str) -> Iterator[re.Match[str]]:
    yield from re.finditer(r"\b(FY[0-9]{2,4})\b", text, flags=re.IGNORECASE)


def _period_distance(period_match: re.Match[str], match_start: int, match_end: int) -> int:
    if period_match.end() <= match_start:
        return match_start - period_match.end()
    if period_match.start() >= match_end:
        return period_match.start() - match_end
    return 0


def _dedupe(
    seen: set[_DedupeKey], fact: ExtractedFact, match: re.Match[str]
) -> ExtractedFact | None:
    period = getattr(fact, "period", None)
    key = (
        fact.label,
        fact.value,
        fact.evidence[0].doc_id,
        fact.evidence[0].chunk_id,
        match.start(),
        match.end(),
        str(period) if period is not None else None,
    )
    if key in seen:
        return None
    seen.add(key)
    return fact
