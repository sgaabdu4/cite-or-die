from cite_or_die.diligence.models import (
    Confidence,
    Escalation,
    ExtractedFact,
    Finding,
    InformationRequest,
    Materiality,
    RiskSeverity,
    Workstream,
)


def build_findings(
    facts: list[ExtractedFact], information_requests: list[InformationRequest]
) -> list[Finding]:
    findings: list[Finding] = []
    by_label = _facts_by_label(facts)

    customer_share = _first(by_label, "Top customer revenue share")
    if customer_share and _to_int(customer_share.value) >= 30:
        findings.append(
            Finding(
                tenant_id=customer_share.tenant_id,
                matter_id=customer_share.matter_id,
                deal_id=customer_share.deal_id,
                title="Top customer concentration",
                summary=(
                    "The top customer share is above the materiality threshold and "
                    "should be tested against renewal and margin dependency."
                ),
                risk_code="customer_concentration",
                workstreams=[Workstream.commercial, Workstream.financial],
                severity=RiskSeverity.high,
                materiality=Materiality.material,
                confidence=Confidence.high,
                evidence=customer_share.evidence,
                owner="commercial lead",
                escalation=Escalation.workstream_lead,
            )
        )

    normalisation = _first(by_label, "EBITDA normalisation add-back")
    recurring = _first(by_label, "Recurring restructuring cost")
    if normalisation and recurring:
        findings.append(
            Finding(
                tenant_id=normalisation.tenant_id,
                matter_id=normalisation.matter_id,
                deal_id=normalisation.deal_id,
                title="Normalisation requires earnings-quality review",
                summary=(
                    "Management add-back overlaps with recurring restructuring cost "
                    "disclosure and may overstate adjusted EBITDA."
                ),
                risk_code="earnings_normalisation",
                workstreams=[Workstream.financial, Workstream.operational],
                severity=RiskSeverity.high,
                materiality=Materiality.material,
                confidence=Confidence.high,
                evidence=normalisation.evidence + recurring.evidence,
                owner="financial lead",
                escalation=Escalation.workstream_lead,
            )
        )

    consent = _first(by_label, "Change of control consent")
    if consent:
        findings.append(
            Finding(
                tenant_id=consent.tenant_id,
                matter_id=consent.matter_id,
                deal_id=consent.deal_id,
                title="Change of control consent required",
                summary=(
                    "A contract requires consent before assignment, creating a "
                    "completion and retention dependency."
                ),
                risk_code="contract_consent",
                workstreams=[Workstream.commercial, Workstream.operational],
                severity=RiskSeverity.high,
                materiality=Materiality.material,
                confidence=Confidence.high,
                evidence=consent.evidence,
                owner="commercial lead",
                escalation=Escalation.deal_lead,
            )
        )

    termination = _first(by_label, "Termination for convenience")
    if termination:
        findings.append(
            Finding(
                tenant_id=termination.tenant_id,
                matter_id=termination.matter_id,
                deal_id=termination.deal_id,
                title="Short termination-for-convenience right",
                summary=(
                    "A termination-for-convenience right can be exercised on a short "
                    "notice period and should be assessed for revenue durability."
                ),
                risk_code="non_standard_clause",
                workstreams=[Workstream.commercial, Workstream.financial],
                severity=RiskSeverity.medium,
                materiality=Materiality.watchlist,
                confidence=Confidence.high,
                evidence=termination.evidence,
                owner="commercial lead",
            )
        )

    for request in information_requests:
        if request.status == "open" and request.delayed_days > 0:
            findings.append(
                Finding(
                    tenant_id=request.tenant_id,
                    matter_id=request.matter_id,
                    deal_id=request.deal_id,
                    title="Delayed open information request",
                    summary=(
                        "An open request is delayed and blocks completeness of the "
                        "workstream review."
                    ),
                    risk_code="open_information_request",
                    workstreams=[Workstream.operational, Workstream.financial],
                    severity=RiskSeverity.medium,
                    materiality=Materiality.watchlist,
                    confidence=Confidence.high,
                    evidence=request.evidence,
                    owner="deal team",
                    escalation=Escalation.workstream_lead,
                )
            )

    return findings


def _facts_by_label(facts: list[ExtractedFact]) -> dict[str, list[ExtractedFact]]:
    grouped: dict[str, list[ExtractedFact]] = {}
    for fact in facts:
        grouped.setdefault(fact.label, []).append(fact)
    return grouped


def _first(
    grouped: dict[str, list[ExtractedFact]], label: str
) -> ExtractedFact | None:
    values = grouped.get(label, [])
    return values[0] if values else None


def _to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
