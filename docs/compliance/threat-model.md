# Threat Model

## Boundaries

- Tenant and matter scope
- Local document store
- Retrieval candidate set
- Provider request payload
- Audit and observability records

## Primary Risks

- Cross-tenant or cross-matter retrieval
- Prompt injection in user input
- Indirect injection in retrieved documents
- Unsupported citations or hallucinated quotes
- PII leakage through logs, traces, or audit payloads

## Controls

- JWT and Casbin authorization
- Tenant/matter-scoped dense, sparse, and graph retrieval
- Input and retrieved-content guardrails
- Verbatim citation verification
- Append-only audit hash chain
- OpenTelemetry attribute deletion plus allowlist redaction
- Adversarial PDF fixtures and mutation gate
