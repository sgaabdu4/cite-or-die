# AI-enabled Due Diligence Acceleration Plan

## Summary

Build an AI-enabled Due Diligence Acceleration product for live mid-market acquisition workflows while preserving cite-or-die's existing RAG and security core as the evidence engine.

The product serves a deal team supporting a PE client acquiring a GBP 100-250m revenue services business. It must work inside a 4-8 week active live deal cycle, use deal-room documents plus structured client data, avoid bespoke model training, keep analysts human-in-the-loop, and cover commercial, operational, and financial workstreams from day one.

## Code/Request Evidence

- Source specification: 6-page PDF supplied by the user. It defines the title/theme, mid-market M&A focus, GBP 100-250m target context, 4-8 week horizon, active transaction deployment approach, bottlenecks, six required capabilities, four expected outputs, and success metrics.
- Existing repo: `README.md` documents tenant/matter scoped retrieval, selected chunks only, verified citations, audit logs, PII redaction, prompt-injection checks, hosted-provider production block, and model provider controls.
- Existing models and service: `src/cite_or_die/core/models.py`, `src/cite_or_die/core/service.py`, and `src/cite_or_die/api/app.py` own auth context, documents, chunks, chat, provider settings, upload, source list, and source file routes.
- Existing storage and retrieval: `src/cite_or_die/storage/repository.py` and `src/cite_or_die/retrieval/service.py` own SQLite document/chunk storage, tenant/matter queries, hybrid retrieval, reranking, and citation graph search.
- Existing controls: `src/cite_or_die/security/walls.py`, `src/cite_or_die/security/citation_verifier.py`, `src/cite_or_die/security/input_guard.py`, `src/cite_or_die/storage/audit.py`, and `src/cite_or_die/security/redaction.py` own matter walls, output scope checks, citation verification, prompt-injection filtering, audit hash chain, and allowlisted audit payloads.
- Existing tests: `tests/integration/test_phase2_walls.py`, `tests/unit/test_audit.py`, `tests/adversarial/test_phase5_adversarial.py`, `tests/eval/test_eval_gate.py`, and `tests/integration/test_phase3_ui.py` already protect key trust behavior.

## Stage Map and Source Status

- Treehouse: done for planning. Continue in the current git worktree.
- Source specification intake: done from PDF text extraction.
- Product/design context: created. `PRODUCT.md`, `DESIGN.md`, `src/cite_or_die/ui/design_tokens.css`, `.impeccable/design.json`, and `.impeccable/live/config.json` exist.
- Grill Me: skipped. The source specification, user constraints, repo evidence, and required demo path resolve scope, product posture, UI flow, proof path, and risk route; no one-question blocker remains.
- Codebase design: done for plan. New diligence behavior gets explicit domain owners and uses the existing RAG core through public service boundaries.
- Test quality: done for plan. Unit, integration, eval, isolation, security, and E2E proof routes are specified below.
- Security review: done for plan. Confidentiality, governance, model-provider, audit, and data exposure controls are listed below.
- E2E: planned for implementation/verification. The plan requires a real UI smoke with desktop and mobile artifacts after the feature exists.

## Decisions

- Keep the existing RAG core as the evidence engine. New diligence workflows call existing ingest, repository, retrieval, provider, citation verification, walls, audit, redaction, and provider config owners instead of duplicating them.
- Add a `cite_or_die.diligence` domain package for deal workspace, source classification, extraction, findings/risk register, cross-workstream links, information-request tracking, report drafts, review workflow, and diligence audit events.
- Store all new diligence objects with `tenant_id`, `matter_id`, and `deal_id`; never query by object ID alone.
- Every AI-assisted extraction, finding, insight, and report claim stores `EvidenceLink[]` back to verified `doc_id`, `chunk_id`, quote, page, and source metadata.
- AI may create draft outputs and suggested findings, but `ReviewStatus` and sign-off remain human-controlled.
- Add synthetic deal-room fixtures only; no real client data.
- Do not train or fine-tune models. Use structured prompts, schema validation, deterministic rules, retrieval scoping, and human review.
- Keep hosted-provider production blocking and selected-evidence model context behavior.

## Domain Language and ADRs

Use these repo-facing terms: AI-enabled Due Diligence Acceleration, mid-market acquisition, live deal cycle, deal team, client, PE client, target business, advisor, diligence accelerator, source specification, product specification.

Avoid adding any blocked context terms named by the user. Run a local deterministic scan before handoff using the exact blocked-term list from the user request; do not persist that list in repo files.

```bash
rg -n -i '<user-specified blocked repo-facing terms>' PRODUCT.md DESIGN.md docs src tests
```

## Product/Design Context

- PRODUCT.md: created at `PRODUCT.md`.
- DESIGN.md: created at `DESIGN.md`.
- Token/design-system owner: `src/cite_or_die/ui/design_tokens.css`.
- Impeccable sidecar: `.impeccable/design.json`.
- Impeccable Live config: `.impeccable/live/config.json`.

## Target Architecture

### Existing Trust Core

- `CiteOrDieService.upload` remains the canonical ingest path for source files.
- `IngestPipeline` keeps source storage, chunking, PII redaction, embedding, sparse index rebuild, and retrieval index updates.
- `RetrievalService.retrieve` remains the only path for evidence sent to model providers.
- `CitationVerifier.verify`, `verify_retrieval_scope`, and `verify_citation_scope` stay required gates.
- `AuditLog.append` keeps allowlisted payloads and hash-chain verification.
- `RuntimeConfigStore` and provider factory keep encrypted per-tenant keys and hosted-model production blocking.

### New Diligence Owners

- `src/cite_or_die/diligence/models.py`: Pydantic models and enums for `Deal`, `Workstream`, `SourceDocument`, `DocumentType`, `ExtractionField`, `ExtractedFact`, `Obligation`, `DateTerm`, `FinancialMetric`, `OperationalMetric`, `CommercialMetric`, `InformationRequest`, `VendorResponse`, `Finding`, `RiskSeverity`, `Materiality`, `Confidence`, `EvidenceLink`, `CrossWorkstreamInsight`, `ReportDraft`, `ReviewStatus`, and `Escalation`.
- `src/cite_or_die/diligence/repository.py`: tenant/matter/deal scoped SQLite tables and query methods for diligence objects.
- `src/cite_or_die/diligence/classification.py`: deterministic and AI-assisted source type and workstream classification with messy filename tolerance.
- `src/cite_or_die/diligence/extraction.py`: schema-bound extraction for contract terms, dates, obligations, clauses, financial normalisations, customer metrics, HR metrics, and operational metrics.
- `src/cite_or_die/diligence/risk.py`: risk scoring, exception creation, gap detection, delayed-response detection, contradiction detection, materiality, owner, and status transitions.
- `src/cite_or_die/diligence/cross_reference.py`: cross-workstream dependency graph linking facts, findings, information requests, vendor responses, and insights.
- `src/cite_or_die/diligence/reporting.py`: cited first-draft workstream outputs and executive risk summary generation.
- `src/cite_or_die/diligence/review.py`: review checkpoints, escalation paths, and human sign-off state transitions.
- `src/cite_or_die/diligence/service.py`: orchestration boundary used by API routes and tests.
- `src/cite_or_die/api/diligence.py`: diligence endpoints mounted by `src/cite_or_die/api/app.py`.
- `src/cite_or_die/ui/diligence_*.js` and `src/cite_or_die/ui/diligence.css`: new UI modules. Do not grow `src/cite_or_die/ui/app.js` or `src/cite_or_die/ui/styles.css` beyond the 700-line split threshold.

### Data Model Shape

Core keys:

- Every table includes `tenant_id`, `matter_id`, `deal_id`, `created_at`, and `updated_at` where stateful.
- Evidence-bearing objects include `evidence_links_json` or normalized evidence link rows.
- Reviewable AI outputs include `confidence`, `review_status`, `reviewed_by`, `reviewed_at`, and `escalation_id`.
- Risk-bearing objects include `severity`, `materiality`, `investment_relevance`, `owner`, `status`, and `source_workstream`.
- Cross-workstream records include `linked_workstreams`, `linked_fact_ids`, `linked_finding_ids`, and rationale evidence.

Suggested tables:

- `diligence_deals`
- `diligence_source_documents`
- `diligence_extracted_facts`
- `diligence_information_requests`
- `diligence_vendor_responses`
- `diligence_findings`
- `diligence_evidence_links`
- `diligence_cross_workstream_insights`
- `diligence_report_drafts`
- `diligence_review_events`

### API Surface

- `POST /diligence/deals`: create a deal workspace inside the active tenant/matter.
- `GET /diligence/deals`: list deal workspaces for the active tenant/matter.
- `POST /diligence/deals/{deal_id}/sources/classify`: classify uploaded source documents and structured client data.
- `POST /diligence/deals/{deal_id}/run`: run extraction, risk register creation, cross-reference generation, and report drafting for selected sources.
- `GET /diligence/deals/{deal_id}/sources`: source library with classification and workstream metadata.
- `GET /diligence/deals/{deal_id}/extractions`: extraction review table.
- `PATCH /diligence/deals/{deal_id}/extractions/{fact_id}`: human review status, corrections, or escalation.
- `GET /diligence/deals/{deal_id}/findings`: risk and exception register.
- `PATCH /diligence/deals/{deal_id}/findings/{finding_id}`: owner, status, materiality, or escalation updates.
- `GET /diligence/deals/{deal_id}/information-requests`: IR tracker.
- `PATCH /diligence/deals/{deal_id}/information-requests/{request_id}`: status, owner, due date, and response linkage.
- `GET /diligence/deals/{deal_id}/insights`: cross-workstream insight layer.
- `POST /diligence/deals/{deal_id}/reports`: generate or refresh cited draft report outputs.
- `GET /diligence/deals/{deal_id}/reports/{report_id}`: cited report draft view.

## UI Flow

Primary workflow:

1. Open the existing app workspace with tenant and matter selected.
2. Enter the diligence accelerator view for the active matter.
3. Create or open a mid-market acquisition deal workspace.
4. Upload or load the synthetic deal room.
5. Classify sources by document type and commercial, operational, or financial workstream.
6. Run extraction and review key terms, dates, obligations, clauses, financial normalisations, customer, HR, and operational metrics.
7. Inspect the risk and exception register sorted by materiality and investment relevance.
8. Open a cross-workstream insight and inspect linked evidence from at least two workstreams.
9. Track an information request through open, delayed, response received, and resolved states.
10. Generate a first-draft diligence output and executive risk summary.
11. Click citations from risk, insight, extraction, and report text into the existing evidence drawer/source viewer.

Required screens/views:

- Deal dashboard
- Source library
- Extraction review table
- Risk and exception register
- Cross-workstream insight view
- IR tracker
- Report draft view
- Evidence drawer/source viewer

Required UI states:

- Empty deal workspace
- Source classification pending/running/failed/complete
- Extraction running/partial/complete
- No evidence available
- Source citation missing from current matter
- Human review needed
- Escalated finding
- Permission denied
- Hosted provider disabled in production

## Vertical Slices and Task Waves

### Wave 1 - Product/design foundation and tracer path

Slice 1: Product/design foundation

- User outcome: repo has product/design context and token owner for diligence UI work.
- Scope: `PRODUCT.md`, `DESIGN.md`, `src/cite_or_die/ui/design_tokens.css`, Impeccable config, UI import, and UI test assertion.
- Acceptance: context gate passes; existing UI still loads; no blocked terms added.
- Verification: context gate, banned-term scan, targeted UI test.

Slice 2: Synthetic deal-room fixture

- User outcome: deterministic test/demo data tells a coherent 4-8 week live-deal story.
- Scope: contracts, financials, org chart, ops reports, customer data, HR records, management deck text, Q&A log, IR list, vendor responses, prior deal precedent, comparable transactions, sector benchmarks, and public market information.
- Acceptance: fixtures include messy names, incomplete documents, contradictions, delayed responses, non-standard clauses, financial normalisation needs, and cross-workstream dependencies.
- Verification: fixture manifest test and eval expected-risk manifest.

Slice 3: Diligence domain skeleton

- User outcome: create a deal workspace and link existing uploaded documents as source documents.
- Scope: `diligence.models`, repository tables, service, API router, tenant/matter/deal scoping, audit event types.
- Acceptance: deal and source records cannot cross tenant or matter boundaries.
- Verification: unit model tests and integration isolation tests.

### Wave 2 - Ingest, classification, and extraction

Slice 4: Source classification

- User outcome: source library classifies VDR documents and structured client data by document type and workstream.
- Scope: classifier, source metadata persistence, UI source library states.
- Acceptance: messy names and incomplete docs are classified with confidence and review status.
- Verification: unit classifier tests, integration upload-to-classify test, UI source-library smoke.

Slice 5: Extraction with evidence

- User outcome: analysts review structured key facts with citations and confidence.
- Scope: extraction schemas, retrieval-scoped provider calls, validation, evidence links, extraction review UI.
- Acceptance: key terms, dates, obligations, clauses, financial normalisations, customer, HR, and ops metrics are stored only when traceable to evidence.
- Verification: unit schema/normalisation tests, provider-context spy test, integration classify-to-extract test.

### Wave 3 - Risk, gaps, contradictions, and cross-reference

Slice 6: Risk and exception register

- User outcome: analysts see prioritised anomalies, non-standard clauses, missing information, delayed responses, contradictions, materiality, owner, and status.
- Scope: risk engine, scoring, review workflow, register UI.
- Acceptance: every finding has severity, materiality, investment relevance, confidence, owner/status, and evidence.
- Verification: unit risk scoring, gap, delayed-response, and contradiction tests; integration extract-to-register test.

Slice 7: Cross-workstream insight layer

- User outcome: users see commercial, operational, and financial dependencies no single stream would catch.
- Scope: cross-reference graph, insight generation, linked evidence UI.
- Acceptance: at least one synthetic insight links facts/findings across two or more workstreams.
- Verification: unit graph tests, integration insight test, eval expected-insight test.

### Wave 4 - Reporting, governance, and demo workflow

Slice 8: Report draft workflow

- User outcome: users generate first-draft diligence outputs by workstream plus executive risk summary.
- Scope: report drafting, citation verification, review status, report UI.
- Acceptance: every report claim is cited; drafts are marked draft/review-needed and never final.
- Verification: unit report drafting tests, integration report-with-citations test.

Slice 9: Governance and audit

- User outcome: reviewers can inspect confidence, review checkpoints, escalation path, and audit trail without raw client content in logs.
- Scope: audit allowlist updates, diligence review events, model-context minimisation tests, escalation workflow.
- Acceptance: audit logs contain IDs/statuses/metadata only; provider receives only retrieved evidence and task instructions.
- Verification: unit audit redaction tests, integration provider-spy test, existing audit/adversarial tests.

Slice 10: E2E demo path

- User outcome: a reviewer can run the complete demo path through the browser.
- Scope: seeded flow, UI automation, desktop/mobile artifacts, E2E project pack.
- Acceptance: load synthetic deal room, run extraction, inspect risk register, open cross-workstream insight, generate draft report, click citations to evidence.
- Verification: automated E2E with screenshots, events, desktop and mobile videos, and report under `docs/e2e/<RUN_ID>/`.

## Acceptance Criteria

- The app demonstrably satisfies all six required capabilities: ingest, extract, flag and prioritise, cross-reference, accelerate reporting, audit and govern.
- It produces all four expected outputs: structured deal knowledge base, risk and exception register, accelerated workstream outputs, and cross-workstream insight layer.
- Every generated risk, extraction, insight, and report claim is traceable to evidence.
- Analysts remain human-in-the-loop; AI does not replace sign-off.
- The demo tells a coherent 4-8 week live-deal story.
- Commercial, operational, and financial workstreams are supported from day one.
- No blocked repo-facing context terms are added.
- Existing RAG/security gates still pass or block readiness with a named repair path.

## Verification Plan

Unit tests:

- `tests/unit/test_diligence_models.py`: schemas, enums, validation, review states, evidence link requirements.
- `tests/unit/test_diligence_classification.py`: document type/workstream classification, messy names, incomplete docs.
- `tests/unit/test_diligence_extraction.py`: key terms, dates, obligations, clauses, metrics, confidence, citation requirements.
- `tests/unit/test_diligence_risk.py`: normalisation, scoring, contradiction/gap detection, delayed response, materiality.
- `tests/unit/test_diligence_reporting.py`: report drafting refuses uncited claims and marks outputs review-needed.
- `tests/unit/test_audit.py`: extended audit allowlist still redacts raw prompts, raw document text, and raw report text.

Integration tests:

- `tests/integration/test_diligence_flow.py`: upload -> classify -> extract -> risk register -> insight -> report draft with verified citations.
- `tests/integration/test_diligence_isolation.py`: new diligence objects cannot cross tenant/matter/deal walls.
- `tests/integration/test_diligence_provider_context.py`: only retrieved evidence reaches model providers.
- Existing `tests/integration/test_phase2_walls.py`, `tests/integration/test_api.py`, and `tests/integration/test_phase3_ui.py` continue to pass.

Eval tests:

- `tests/eval/test_diligence_expected_risks.py`: synthetic deal-room expected risks and insights are found with evidence.
- Existing `tests/eval/test_eval_gate.py` and citation graph evals continue to pass.

Security and adversarial:

- Existing adversarial PDF tests continue to pass.
- Add diligence fixture with an indirect prompt-injection source and verify the retrieved-content guard rejects it.
- Add audit proof that diligence audit events store IDs, statuses, and review metadata only.

E2E:

- Scaffold/update `docs/e2e/project.json`.
- Add an automated browser flow for the demo path.
- Capture `events.jsonl`, step screenshots, desktop and mobile videos, 2x recaps where supported, logs, and `report.md`.

Suggested commands:

```bash
node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all .
rg -n -i '<user-specified blocked repo-facing terms>' PRODUCT.md DESIGN.md docs src tests
uv run --extra dev python -m pytest tests/unit/test_diligence_models.py tests/unit/test_diligence_classification.py tests/unit/test_diligence_extraction.py tests/unit/test_diligence_risk.py tests/unit/test_diligence_reporting.py
uv run --extra dev python -m pytest tests/integration/test_diligence_flow.py tests/integration/test_diligence_isolation.py tests/integration/test_diligence_provider_context.py
uv run --extra dev python -m pytest tests/eval/test_diligence_expected_risks.py tests/eval/test_eval_gate.py tests/adversarial/test_phase5_adversarial.py
uv run --extra dev python -m pytest tests/integration/test_phase2_walls.py tests/integration/test_api.py tests/integration/test_phase3_ui.py tests/unit/test_audit.py
uv run --extra dev ruff check .
uv run --extra dev mypy
uv run --extra dev pyrefly check
test ! -f he-state.json || node "$HOME/.agents/scripts/he-state.mjs" validate he-state.json
```

## Traceability

| Requirement | Slice/task | Acceptance criteria | Verification |
|---|---|---|---|
| Ingest deal-room documents and structured client data | S2, S3, S4 | Source records classify by document type/workstream with metadata | Fixture manifest, classify integration test |
| Extract and normalise key data points | S5 | Facts and metrics require evidence and confidence | Extraction and normalisation tests |
| Flag and prioritise risks | S6 | Findings include severity, materiality, owner, status, evidence | Risk unit tests and register integration |
| Cross-reference workstreams | S7 | Insights link multiple workstreams and evidence | Cross-reference tests and expected-insight eval |
| Accelerate reporting | S8 | Drafts are cited and review-needed | Report unit and integration tests |
| Audit and govern | S9 | Confidence, review, escalation, audit redaction, provider minimisation | Audit, provider-spy, adversarial tests |
| Expected outputs | S3-S8 | Knowledge base, register, outputs, insight layer exist | Integration flow and E2E |
| Existing trust core preserved | All slices | Existing isolation, citation, audit, guardrail tests pass | Existing test suite subset plus gates |

## High-Risk Controls

- Tenant/matter/deal isolation: every repository method filters by tenant, matter, and deal in the same query; tests attempt cross-scope reads and updates.
- Model provider minimisation: all diligence generation uses retrieved chunks or verified extracted facts only; provider-spy tests assert no full document library, raw source file, or unrelated matter data is sent.
- Audit minimisation: extend `ALLOWED_AUDIT_KEYS` only with IDs/statuses/counts/review metadata; do not log raw prompts, source text, vendor response text, report prose, or full extracted clauses.
- Human review: `ReviewStatus` defaults to `needs_review`; only authenticated users can mark reviewed, escalated, or resolved.
- Hosted model boundary: keep production hosted-provider block; surface disabled state in the UI when relevant.
- Prompt-injection boundary: scan user text and retrieved chunks before model calls; add diligence fixture coverage for hostile deal-room text.
- Schema/state changes: require migration notes, rollback plan, and audit expectations for every new SQLite table.
- UI split: new diligence modules instead of growing near-threshold UI files past 700 lines.

## Risks

- Data model breadth may sprawl. Mitigation: start with a tracer slice and typed models, then add fields only when tied to an acceptance test.
- Extraction accuracy can be overstated. Mitigation: confidence, evidence links, review state, and refusals for uncited claims.
- Cross-workstream insights can become vague. Mitigation: require linked facts/findings from at least two workstreams plus evidence.
- Report drafts can look too final. Mitigation: visible draft/review-needed state and no final sign-off language.
- UI density can hurt accessibility. Mitigation: token owner, WCAG 2.1 AA target, keyboard/focus tests, desktop/mobile E2E.

## Unknowns

None blocking Plan. Implementation may discover exact fixture file formats or route naming adjustments; those must stay inside the architecture and proof path above.

## Artifact Choice

Use both PRD and vertical-slice content in this single `plan.md`. External tracker issue creation is out of scope unless explicitly requested later.

## Next

Ready target for `/he:implement` after context gates pass:

```text
/he:implement

Worktree: current git worktree
State: local ignored he-state.json, when present
Read docs/planning/ai-enabled-due-diligence-acceleration/plan.md first, then local he-state.json if present.

Implement the AI-enabled Due Diligence Acceleration plan while preserving the existing RAG/security core. Start with the synthetic fixture and diligence domain skeleton, use TDD, keep new diligence objects tenant/matter/deal scoped, require evidence links for AI-assisted outputs, keep analysts human-in-the-loop, and maintain the blocked-term guard.
```
