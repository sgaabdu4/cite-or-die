# Threat Model

## Boundaries

- Tenant and matter scope
- Local document store
- Diligence deal/object store
- Retrieval candidate set
- Diligence source document set
- Provider request payload
- Audit and observability records

## Primary Risks

- Cross-tenant or cross-matter retrieval
- Cross-deal diligence object reads or writes
- Prompt injection in user input
- Indirect injection in retrieved documents
- Unsupported citations or hallucinated quotes
- Unsupported diligence findings or report claims
- PII leakage through logs, traces, or audit payloads
- Draft diligence output mistaken for final sign-off

## Controls

- JWT and Casbin authorization
- Tenant/matter-scoped dense, sparse, and graph retrieval
- Tenant/matter/deal-scoped diligence repository queries
- Evidence links required on facts, findings, insights, and report claims
- Review-needed defaults on generated diligence outputs
- Input and retrieved-content guardrails
- Verbatim citation verification
- Append-only audit hash chain with serialized SQLite appends
- OpenTelemetry attribute deletion plus allowlist redaction
- Diligence audit payload allowlist for IDs, statuses, and counts only
- Adversarial PDF fixtures, diligence isolation tests, and mutation gate
