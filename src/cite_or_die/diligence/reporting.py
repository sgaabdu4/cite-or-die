from cite_or_die.diligence.models import (
    Deal,
    Finding,
    ReportClaim,
    ReportDraft,
    Workstream,
)


def build_report_drafts(deal: Deal, findings: list[Finding]) -> list[ReportDraft]:
    if not findings:
        return []

    drafts = [
        ReportDraft(
            tenant_id=deal.tenant_id,
            matter_id=deal.matter_id,
            deal_id=deal.deal_id,
            title="Executive Risk Summary",
            workstream=None,
            claims=[_claim(finding) for finding in findings],
        )
    ]
    for workstream in (
        Workstream.commercial,
        Workstream.operational,
        Workstream.financial,
    ):
        workstream_findings = [
            finding for finding in findings if workstream in finding.workstreams
        ]
        if workstream_findings:
            drafts.append(
                ReportDraft(
                    tenant_id=deal.tenant_id,
                    matter_id=deal.matter_id,
                    deal_id=deal.deal_id,
                    title=f"{workstream.value.title()} Workstream Draft",
                    workstream=workstream,
                    claims=[_claim(finding) for finding in workstream_findings],
                )
            )
    return drafts


def _claim(finding: Finding) -> ReportClaim:
    return ReportClaim(
        text=f"{finding.title}: {finding.summary}",
        evidence=finding.evidence,
    )
