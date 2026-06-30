from cite_or_die.diligence.models import (
    Confidence,
    CrossWorkstreamInsight,
    Deal,
    Finding,
    Workstream,
)


def build_insights(deal: Deal, findings: list[Finding]) -> list[CrossWorkstreamInsight]:
    insights: list[CrossWorkstreamInsight] = []
    by_code = {finding.risk_code: finding for finding in findings}

    customer = by_code.get("customer_concentration")
    earnings = by_code.get("earnings_normalisation")
    if customer and earnings:
        insights.append(
            CrossWorkstreamInsight(
                tenant_id=deal.tenant_id,
                matter_id=deal.matter_id,
                deal_id=deal.deal_id,
                title="Customer concentration affects earnings diligence",
                summary=(
                    "Commercial concentration and earnings-quality findings should be "
                    "reviewed together because revenue dependency can amplify adjusted "
                    "EBITDA risk."
                ),
                workstreams=[Workstream.commercial, Workstream.financial],
                confidence=Confidence.high,
                evidence=customer.evidence + earnings.evidence,
            )
        )

    consent = by_code.get("contract_consent")
    open_request = by_code.get("open_information_request")
    if consent and open_request:
        insights.append(
            CrossWorkstreamInsight(
                tenant_id=deal.tenant_id,
                matter_id=deal.matter_id,
                deal_id=deal.deal_id,
                title="Contract consent depends on open workstream evidence",
                summary=(
                    "The consent dependency should be tracked with open requests so "
                    "completion risk is escalated before decision deadlines."
                ),
                workstreams=[Workstream.commercial, Workstream.operational],
                confidence=Confidence.high,
                evidence=consent.evidence + open_request.evidence,
            )
        )

    return insights
