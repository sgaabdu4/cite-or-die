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

            for label, pattern, unit in (
                (
                    "Revenue",
                    r"\brevenues?(?:\s+(?:is|was|were|of|total(?:ed|led)?|reported at))?"
                    r"\s*(?:[:♦-]\s*)?"
                    r"(?:GBP|£)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)?\b",
                    "GBP m",
                ),
                (
                    "Reported EBITDA",
                    r"\b(?:reported|adjusted)?\s*EBITDA\s+"
                    r"(?:is|was|of|total(?:ed|led)?|reported at)?\s*"
                    r"(?:[:♦-]\s*)?"
                    r"(?:GBP|£)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)?\b",
                    "GBP m",
                ),
                (
                    "EBITDA normalisation add-back",
                    r"\bnormalisation\s+(?:adds|add-back(?:s)?(?: of)?|adjustment(?:s)?(?: of)?)\s*"
                    r"(?:GBP|£)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)?\b",
                    "GBP m",
                ),
                (
                    "Recurring restructuring cost",
                    r"\brecurring restructuring costs?\s+(?:are|were|of|total(?:ed|led)?)\s*"
                    r"(?:GBP|£)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:m|million)?\b",
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
                                value=_number_value(match.group(1)),
                                period=_period_for_match(text, match),
                                unit=unit,
                                confidence=Confidence.high,
                                evidence=[evidence],
                            ),
                            match,
                        )
                    )

            for customer_share in _customer_share_matches(text):
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

            for customer_group_share in _customer_group_share_matches(text):
                evidence = _evidence(chunk, customer_group_share)
                facts.append(
                    _dedupe(
                        seen,
                        CommercialMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.commercial,
                            label="Top customer group revenue share",
                            value=customer_group_share.group(1),
                            unit="percent",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                        customer_group_share,
                    )
                )

            for churn in re.finditer(
                r"\b(?:customer\s+)?churn\s+(?:is|was|of|reached)\s*([0-9]+)\s*(?:percent|%)",
                text,
                flags=re.IGNORECASE,
            ):
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
                r"\butili[sz]ation\s+(?:at|of|was)\s*([0-9]+)\s*(?:percent|%)",
                text,
                flags=re.IGNORECASE,
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

            for backlog in _sla_backlog_matches(text):
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
                r"\b(?:regretted\s+)?attrition\s+(?:of|was|reached)\s*"
                r"([0-9]+)\s*(?:percent|%)",
                text,
                flags=re.IGNORECASE,
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

            vacancy_pattern = (
                r"\b([0-9]+)\s+open vacancies\b|"
                r"\bopen vacancies\s+(?:of|were|total(?:ed|led)?)\s*([0-9]+)\b"
            )
            for vacancy in re.finditer(vacancy_pattern, text, flags=re.IGNORECASE):
                value = vacancy.group(1) or vacancy.group(2)
                evidence = _evidence(chunk, vacancy)
                facts.append(
                    _dedupe(
                        seen,
                        OperationalMetric(
                            tenant_id=source.tenant_id,
                            matter_id=source.matter_id,
                            deal_id=source.deal_id,
                            workstream=Workstream.operational,
                            label="Open vacancies",
                            value=value,
                            unit="vacancies",
                            confidence=Confidence.high,
                            evidence=[evidence],
                        ),
                        vacancy,
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

            seen_request_sentences: set[str] = set()
            for information_request in _open_request_matches(text):
                request_sentence = _matched_sentence(text, information_request)
                if request_sentence in seen_request_sentences:
                    continue
                seen_request_sentences.add(request_sentence)
                delay = re.search(
                    r"delayed(?: by)?\s*([0-9]+)\s*days",
                    request_sentence,
                    flags=re.IGNORECASE,
                )
                if _is_open_request_status(request_sentence, delay):
                    delayed_days = int(delay.group(1)) if delay else 0
                    evidence = _evidence(chunk, information_request)
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

            vendor_response = _vendor_response_match(text)
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


def _customer_share_matches(text: str) -> Iterator[re.Match[str]]:
    patterns = (
        r"\btop customer\s+(?:represents|represented|accounts for|accounted for|made up|"
        r"comprised)\s*([0-9]+)\s*(?:percent|%)",
        r"\blargest customer\s+(?:represents|represented|accounts for|accounted for|made up|"
        r"comprised)\s*([0-9]+)\s*(?:percent|%)",
        r"\bcustomer [A-Z]\s+(?:represents|represented|accounts for|accounted for|made up|"
        r"comprised)\s*([0-9]+)\s*(?:percent|%)",
        r"\brevenues?\s+from\s+one\s+customer\b[\s\S]{0,240}?"
        r"\(([0-9]+)\s*%\)",
        r"\brevenues?\s+from\s+one\s+customer\b[\s\S]{0,240}?"
        r"(?:represent(?:s|ed)?|accounts? for|accounted for|made up|comprised)"
        r"\s*(?:approximately\s*)?([0-9]+)\s*(?:percent|%)",
        r"\btop customer\b[\s\S]{0,120}?"
        r"(?:represent(?:s|ed)?|accounts? for|accounted for|made up|comprised)"
        r"\s*(?:approximately\s*)?([0-9]+)\s*(?:percent|%)",
        r"\blargest customer\b[\s\S]{0,120}?"
        r"(?:represent(?:s|ed)?|accounts? for|accounted for|made up|comprised)"
        r"\s*(?:approximately\s*)?([0-9]+)\s*(?:percent|%)",
    )
    for pattern in patterns:
        yield from re.finditer(pattern, text, flags=re.IGNORECASE)


def _customer_group_share_matches(text: str) -> Iterator[re.Match[str]]:
    patterns = (
        r"\btop (?:two|three|[0-9]+)(?:\s+\w+){0,3}\s+customers?\s+"
        r"(?:represent|represented|account for|accounted for|made up|comprised)\s*"
        r"([0-9]+)\s*(?:percent|%)",
        r"\b(?:two|three|[0-9]+)(?:\s+\w+){0,3}\s+customers?\s+"
        r"(?:represent|represented|account for|accounted for|made up|comprised)\s*"
        r"([0-9]+)\s*(?:percent|%)",
    )
    for pattern in patterns:
        yield from re.finditer(pattern, text, flags=re.IGNORECASE)


def _sla_backlog_matches(text: str) -> Iterator[re.Match[str]]:
    patterns = (
        r"\bSLA backlog\s+(?:at|of|was)\s*([0-9]+)\s*days\b",
        r"\bbacklog\s+(?:at|of|was|aged)\s*([0-9]+)\s*days\b",
        r"\b([0-9]+)\s*days?\s+(?:of\s+)?(?:SLA\s+)?backlog\b",
    )
    for pattern in patterns:
        yield from re.finditer(pattern, text, flags=re.IGNORECASE)


def _open_request_matches(text: str) -> Iterator[re.Match[str]]:
    yield from re.finditer(
        r"\b(information request|request list|IR list|open item|open request)\b",
        text,
        flags=re.IGNORECASE,
    )


def _is_open_request_status(sentence: str, delay: re.Match[str] | None) -> bool:
    if _is_closed_request_status(sentence):
        return False
    return bool(
        delay
        or re.search(
            r"\b(open|outstanding|unresolved|overdue)\b",
            sentence,
            flags=re.IGNORECASE,
        )
    )


def _is_closed_request_status(sentence: str) -> bool:
    if re.search(
        r"\b(closed|resolved|completed|complete|fulfilled|answered)\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return True
    if re.search(
        r"\b(?:not|never)\s+(?:\w+\s+){0,3}provided\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return False
    if re.search(
        r"\b(?:until|unless|before|once|when)\b[^.!?]{0,160}\bprovided\b",
        sentence,
        flags=re.IGNORECASE,
    ):
        return False
    return bool(re.search(r"\bprovided\b", sentence, flags=re.IGNORECASE))


def _vendor_response_match(text: str) -> re.Match[str] | None:
    return re.search(
        r"\b(vendor response|seller response|response states|response does not provide)\b",
        text,
        flags=re.IGNORECASE,
    )


def _required_consent_matches(text: str) -> Iterator[re.Match[str]]:
    for match in re.finditer(r"\bchange of control\b", text, flags=re.IGNORECASE):
        sentence = _matched_sentence(text, match)
        if _is_negated_phrase(sentence, "change of control"):
            continue
        if _is_negated_consent_requirement(sentence):
            continue
        has_approval = re.search(r"\b(consent|approval)\b", sentence, flags=re.IGNORECASE)
        has_requirement = re.search(
            r"\b(requires?|required|needed|prior|written)\b|"
            r"\bmust\s+be\s+(obtained|secured)\b",
            sentence,
            flags=re.IGNORECASE,
        )
        if has_approval and has_requirement:
            yield match


def _termination_notice_matches(text: str) -> Iterator[re.Match[str]]:
    notice_days = (
        r"(?:at\s+least\s+)?(?:\{\s*)?(?:[a-z]+(?:\s+|-))?"
        r"\(?\s*([0-9]+)\s*\)?(?:\s*\})?"
        r"\s*-?\s*days?[’']?\s+"
    )
    patterns = (
        r"\btermination for convenience\b[^.!?]{0,240}?"
        + notice_days
        + r"(?:prior\s+)?"
        r"(?:written\s+)?notice\b",
        r"\beither party may terminate this agreement\b[^.!?]{0,240}?"
        r"\b(?:for any reason|for no reason|without cause)\b[^.!?]{0,240}?"
        + notice_days
        + r"(?:prior\s+)?"
        r"(?:written\s+)?notice\b",
        r"\bterminate for convenience\b[^.!?]{0,240}?"
        + notice_days
        + r"(?:prior\s+)?"
        r"(?:written\s+)?notice\b",
        r"\bterminate this agreement for convenience\b[^.!?]{0,240}?"
        + notice_days
        + r"(?:prior\s+)?"
        r"(?:written\s+)?notice\b",
        r"\bterminate this agreement\b[^.!?]{0,120}?\bfor convenience\b[^.!?]{0,240}?"
        + notice_days
        + r"(?:prior\s+)?"
        r"(?:written\s+)?notice\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            sentence = _matched_sentence(text, match)
            if not _is_negated_termination_for_convenience(sentence):
                yield match


def _number_value(value: str) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else value


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


def _is_negated_termination_for_convenience(sentence: str) -> bool:
    lower = sentence.casefold()
    return bool(
        _is_negated_phrase(sentence, "termination for convenience")
        or re.search(
            r"\b(?:may|shall|will|can|could|should|would|must)\s+not\s+terminate\b"
            r"[^.!?]{0,160}\bfor convenience\b",
            lower,
        )
        or re.search(
            r"\b(?:neither|no)\s+party\s+(?:may|shall|will|can|could|should|would|must)\s+"
            r"terminate\b[^.!?]{0,160}\bfor convenience\b",
            lower,
        )
        or re.search(
            r"\b(?:cannot|can't)\s+terminate\b[^.!?]{0,160}\bfor convenience\b",
            lower,
        )
        or re.search(
            r"\bnot\s+(?:entitled|permitted|allowed)\s+to\s+terminate\b"
            r"[^.!?]{0,160}\bfor convenience\b",
            lower,
        )
    )


def _is_negated_consent_requirement(sentence: str) -> bool:
    lower = sentence.casefold()
    patterns = (
        r"\b(?:does|do|did)\s+not\s+require\b[^.!?]{0,120}\b(consent|approval)\b",
        r"\b(consent|approval)\b\s+(?:is|are|was|were)\s+not\s+(required|needed)\b",
        r"\b(consent|approval)\b\s+(?:shall|will|may|must|should|can|could)\s+not\s+"
        r"(?:be\s+)?(?:required|needed|obtained|secured)\b",
        r"\bno\s+(consent|approval)\s+(?:is\s+)?(?:required|needed)\b",
    )
    return bool(
        _is_negated_phrase(sentence, "consent")
        or _is_negated_phrase(sentence, "approval")
        or any(re.search(pattern, lower) for pattern in patterns)
    )


def _matched_sentence(text: str, match: re.Match[str]) -> str:
    start = match.start()
    end = match.end()
    left = start
    while left > 0 and not _is_sentence_boundary(text, left - 1):
        left -= 1
    right = end
    while right < len(text) and not _is_sentence_boundary(text, right):
        right += 1
    if right < len(text):
        right += 1
    sentence = " ".join(text[left:right].strip().split())
    return sentence[:500] if sentence else _first_sentence(text)


def _first_sentence(text: str) -> str:
    stripped = " ".join(text.strip().split())
    parts = re.split(r"(?<=[.!?])\s+", stripped)
    return parts[0][:500] if parts and parts[0] else stripped[:500]


def _is_sentence_boundary(text: str, index: int) -> bool:
    marker = text[index]
    if marker == ".":
        previous_is_digit = index > 0 and text[index - 1].isdigit()
        next_is_digit = index + 1 < len(text) and text[index + 1].isdigit()
        if previous_is_digit and next_is_digit:
            return False
    return marker in ".!?"


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
