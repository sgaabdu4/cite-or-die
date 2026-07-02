# Threat Model

## Boundaries

- Tenant and matter scope
- Local document store
- Pseudonymized evidence preview and entity map store
- Diligence deal/object store
- Retrieval candidate set
- Diligence source document set
- Provider request payload
- Provider base URL and outbound connection target
- Audit and observability records

## Primary Risks

- Cross-tenant or cross-matter retrieval
- Cross-deal diligence object reads or writes
- Prompt injection in user input
- Indirect injection in retrieved documents
- Unsupported citations or hallucinated quotes
- Unsupported diligence findings or report claims
- Over-broad AI-assisted diligence context
- PII leakage through logs, traces, or audit payloads
- Entity placeholder map tamper or cross-scope reuse
- Provider settings tamper or unreadability after secret rotation
- SSRF or private-network access through provider base URLs
- Raw provider error or malformed-response leakage
- Draft diligence output mistaken for final sign-off

## Controls

- JWT and Casbin authorization
- Tenant/matter-scoped dense, sparse, and graph retrieval
- Tenant/matter/deal-scoped diligence repository queries
- Per-tenant/matter encrypted entity maps with invalid-map fail-closed behavior
- Provider base URL allowlist, local-provider port checks, DNS/private-IP blocking, and guarded HTTP transport
- Evidence links required on facts, findings, insights, and report claims
- AI-assisted diligence uses only cited evidence chunks after the baseline review
- AI-assisted transient retry plus controlled error mapping for provider
  HTTP, network, malformed-response, and citation failures
- Per-tenant encrypted provider settings fail closed when tampered or decrypted
  with the wrong `auth_secret`
- Review-needed defaults on generated diligence outputs
- Input and retrieved-content guardrails
- Verbatim citation verification
- Append-only audit hash chain with serialized SQLite appends
- OpenTelemetry attribute deletion plus allowlist redaction
- Diligence audit payload allowlist for IDs, statuses, and counts only
- Adversarial PDF fixtures, diligence isolation tests, and mutation gate
