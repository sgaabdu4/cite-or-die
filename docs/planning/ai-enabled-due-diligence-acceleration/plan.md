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
- Product/design context: implemented. `PRODUCT.md`, `DESIGN.md`, `src/cite_or_die/ui/design_tokens.css`, `.impeccable/design.json`, and `.impeccable/live/config.json` exist.
- Grill Me: skipped. The source specification, user constraints, repo evidence, and required demo path resolve scope, product posture, UI flow, proof path, and risk route; no one-question blocker remains.
- Codebase design: implemented for the tracer. New diligence behavior has explicit domain owners and uses the existing upload, repository, scope, audit, and source-viewer boundaries.
- Test quality: implemented for the tracer. Unit, integration, eval, isolation, API, UI, and E2E proof routes are listed below.
- Security review: implemented for the tracer. Tenant/matter/deal scope, evidence requirements, review defaults, and audit minimisation are listed below.
- E2E: implemented as `tests/e2e/diligence_workflow.mjs` with project pack docs under `docs/e2e/`.

## Decisions

- Keep the existing RAG core as the evidence engine. The implemented diligence tracer calls existing upload, repository, scope verification, audit, redaction, and source-viewer owners instead of duplicating them.
- Add a `cite_or_die.diligence` domain package for deal workspace, source classification, extraction, findings/risk register, cross-workstream links, information-request tracking, report drafts, and diligence audit events.
- Store all new diligence objects with `tenant_id`, `matter_id`, and `deal_id`; never query by object ID alone.
- Every extraction, finding, insight, and report claim stores `EvidenceLink[]` back to `doc_id`, `chunk_id`, quote, page, and source metadata.
- Generated report drafts default to `ReviewStatus.needs_review`; final sign-off remains outside the tracer.
- Add synthetic deal-room fixtures only; no real client data.
- Do not train or fine-tune models. The current tracer uses schema validation, deterministic rules, retrieval scoping, and human review state without calling hosted model providers.
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

### Implemented Diligence Owners

- `src/cite_or_die/diligence/models.py`: Pydantic models and enums for `Deal`, `Workstream`, `SourceDocument`, `DocumentType`, `ExtractionField`, `ExtractedFact`, `Obligation`, `DateTerm`, `FinancialMetric`, `OperationalMetric`, `CommercialMetric`, `InformationRequest`, `VendorResponse`, `Finding`, `RiskSeverity`, `Materiality`, `Confidence`, `EvidenceLink`, `CrossWorkstreamInsight`, `ReportDraft`, `ReviewStatus`, and `Escalation`.
- `src/cite_or_die/diligence/repository.py`: tenant/matter/deal scoped SQLite tables and query methods for diligence objects.
- `src/cite_or_die/diligence/classification.py`: deterministic source type and workstream classification with messy filename tolerance.
- `src/cite_or_die/diligence/extraction.py`: rule-based extraction for contract terms, obligations, clauses, financial normalisations, customer metrics, HR metrics, operational metrics, delayed information requests, and vendor responses.
- `src/cite_or_die/diligence/risk.py`: risk finding creation for customer concentration, earnings normalisation, contract consent, non-standard termination clauses, delayed requests, materiality, owner, and escalation defaults.
- `src/cite_or_die/diligence/cross_reference.py`: deterministic cross-workstream insight builder linking compatible findings and their evidence.
- `src/cite_or_die/diligence/reporting.py`: cited first-draft workstream outputs and executive risk summary generation.
- `src/cite_or_die/diligence/service.py`: orchestration boundary used by API routes and tests.
- `src/cite_or_die/api/diligence.py`: diligence endpoints mounted by `src/cite_or_die/api/app.py`.
- `src/cite_or_die/ui/diligence.js` and `src/cite_or_die/ui/diligence.css`: new UI module and styles. `src/cite_or_die/ui/app.js` only wires the module and evidence drawer event.

### Data Model Shape

Core keys and storage:

- `Deal` includes `tenant_id`, `matter_id`, `deal_id`, revenue band, horizon, optional `source_doc_ids`, and `created_at`.
- Source, fact, request, response, finding, insight, and report objects include `tenant_id`, `matter_id`, and `deal_id`.
- Evidence-bearing objects carry embedded `EvidenceLink` values with source quote, document, chunk, filename, tenant, matter, and optional page or source-field metadata.
- Reviewable findings, insights, and report drafts default to `needs_review`.

Implemented tables:

- `diligence_deals`
- `diligence_sources`
- `diligence_facts`
- `diligence_information_requests`
- `diligence_vendor_responses`
- `diligence_findings`
- `diligence_insights`
- `diligence_reports`

### API Surface

- `POST /diligence/deals`: create a deal workspace inside the active tenant/matter.
- `POST /diligence/deals/{deal_id}/sources/classify`: classify uploaded source documents, including uploaded structured client-data exports.
- `POST /diligence/deals/{deal_id}/run`: run extraction, risk register creation, cross-reference generation, and report drafting for selected sources.
- `GET /diligence/deals/{deal_id}/findings`: risk and exception register.
- `GET /diligence/deals/{deal_id}/reports`: cited report draft list.

`POST /diligence/deals` validates `target_revenue_gbp_m` in the 100-250 range,
`horizon_weeks` in the 4-8 range, and up to 50 optional `source_doc_ids`.

## UI Flow

Primary workflow:

1. Open the existing app workspace with tenant and matter selected.
2. Use the diligence accelerator section in the app shell.
3. Click **Load sample deal room** to upload six safe text sources, create `Project Northstar`, and classify the sources, or select existing matter sources and click **Review selected sources**.
4. Click **Run diligence review** to extract facts, build findings, generate cross-workstream insights, track delayed information requests, and create report drafts.
5. Review Source library, Extraction review, Risk register, Cross-workstream insights, IR tracker, and Report drafts tabs.
6. Click evidence buttons from risk, insight, extraction, or report text into the existing evidence drawer/source viewer.

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
- Source classification pending/running/failed/complete through status text and disabled buttons
- Accelerator running/complete/failed through status text and disabled buttons
- No evidence available
- Source citation missing from current matter
- Human review needed
- Permission denied
- Workspace changed reset

## Vertical Slices and Task Waves

### Wave 1 - Product/design foundation and tracer path

Slice 1: Product/design foundation

- User outcome: repo has product/design context and token owner for diligence UI work.
- Scope: `PRODUCT.md`, `DESIGN.md`, `src/cite_or_die/ui/design_tokens.css`, Impeccable config, UI import, and UI test assertion.
- Acceptance: context gate passes; existing UI still loads; no blocked terms added.
- Verification: context gate, banned-term scan, targeted UI test.

Slice 2: Synthetic deal-room fixture

- User outcome: deterministic test/demo data tells a coherent 4-8 week live-deal story.
- Scope: six UI-seeded text sources covering contract, financial, operations, customer data, HR records, Q&A/IR, and vendor response content.
- Acceptance: fixtures include delayed responses, non-standard clauses, financial normalisation needs, customer concentration, and cross-workstream dependencies.
- Verification: integration flow, UI wiring test, E2E workflow, and expected-risk eval.

Slice 3: Diligence domain skeleton

- User outcome: create a deal workspace and link existing uploaded documents as source documents.
- Scope: `diligence.models`, repository tables, service, API router, tenant/matter/deal scoping, audit event types.
- Acceptance: deal and source records cannot cross tenant or matter boundaries.
- Verification: unit model tests and integration isolation tests.

### Wave 2 - Ingest, classification, and extraction

Slice 4: Source classification

- User outcome: source library classifies VDR documents and structured client data by document type and workstream.
- Scope: classifier, source metadata persistence, UI source library states.
- Acceptance: messy names and source content are classified with document type, workstream, and confidence.
- Verification: unit classifier tests, integration API/flow tests, and UI source-library smoke.

Slice 5: Extraction with evidence

- User outcome: analysts review structured key facts with citations and confidence.
- Scope: deterministic extraction rules, Pydantic validation, evidence links, extraction review UI.
- Acceptance: obligations, clauses, financial normalisations, customer, HR, and ops metrics are stored only when traceable to evidence.
- Verification: unit model/extraction tests and integration flow/API tests.

### Wave 3 - Risk and cross-reference

Slice 6: Risk and exception register

- User outcome: analysts see prioritised concentration, normalisation, consent, non-standard clause, and delayed-request findings.
- Scope: risk engine, materiality/severity, owner/escalation defaults, and register UI.
- Acceptance: every finding has severity, materiality, confidence, owner/status where available, and evidence.
- Verification: unit risk tests, expected-risk eval, and integration flow/API tests.

Slice 7: Cross-workstream insight layer

- User outcome: users see commercial, operational, and financial dependencies no single stream would catch.
- Scope: deterministic finding cross-reference rules, insight generation, linked evidence UI.
- Acceptance: at least one synthetic insight links facts/findings across two or more workstreams.
- Verification: integration flow and E2E workflow inspect cross-workstream insights.

### Wave 4 - Reporting, governance, and demo workflow

Slice 8: Report draft workflow

- User outcome: users generate first-draft diligence outputs by workstream plus executive risk summary.
- Scope: report drafting from findings, evidence links, review status, report UI.
- Acceptance: every report claim is cited; drafts are marked draft/review-needed and never final.
- Verification: model/repository tests, integration flow/API tests, and E2E workflow.

Slice 9: Governance and audit

- User outcome: reviewers can inspect confidence, review status, escalation defaults, and audit trail without raw client content in logs.
- Scope: audit allowlist updates and diligence event creation.
- Acceptance: audit logs contain IDs, statuses, and counts only; current diligence runs do not call hosted providers.
- Verification: diligence isolation audit test plus existing audit/adversarial tests.

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
- `tests/unit/test_diligence_risk.py`: customer concentration selection and short termination notice scoring.
- `tests/unit/test_diligence_repository.py`: scoped persistence, rollback, and typed fact round-trip.
- Existing `tests/unit/test_audit.py`: audit chain behavior remains intact.

Integration tests:

- `tests/integration/test_diligence_flow.py`: upload -> classify -> extract -> risk register -> insight -> report draft with verified citations.
- `tests/integration/test_diligence_isolation.py`: new diligence objects cannot cross tenant/matter/deal walls.
- `tests/integration/test_diligence_api.py`: public diligence routes create, classify, run, and read outputs.
- `tests/integration/test_diligence_ui.py`: app shell wires the diligence workspace, CSS, API paths, state, and evidence events.
- Existing `tests/integration/test_phase2_walls.py`, `tests/integration/test_api.py`, and `tests/integration/test_phase3_ui.py` continue to protect the trust core.

Eval tests:

- `tests/eval/test_diligence_expected_risks.py`: synthetic deal-room expected risks are found with evidence.
- Existing `tests/eval/test_eval_gate.py` and citation graph evals continue to pass.

Security and adversarial:

- Existing adversarial PDF tests continue to pass.
- `tests/integration/test_diligence_isolation.py` verifies viewer write denial, cross-scope read denial, and diligence audit payload minimisation.

E2E:

- `docs/e2e/project.json` describes the local seeded-test target.
- `tests/e2e/diligence_workflow.mjs` automates the demo path on desktop and mobile profiles.
- The runner writes `events.jsonl`, step screenshots, videos, logs, `state.json`, `issues.md`, `regression.md`, and `report.md` under `docs/e2e/<RUN_ID>/`.

Suggested commands:

```bash
node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all .
rg -n -i '<user-specified blocked repo-facing terms>' PRODUCT.md DESIGN.md docs src tests
uv run --extra dev python -m pytest tests/unit/test_diligence_models.py tests/unit/test_diligence_classification.py tests/unit/test_diligence_extraction.py tests/unit/test_diligence_risk.py tests/unit/test_diligence_repository.py
uv run --extra dev python -m pytest tests/integration/test_diligence_api.py tests/integration/test_diligence_flow.py tests/integration/test_diligence_isolation.py tests/integration/test_diligence_ui.py
uv run --extra dev python -m pytest tests/eval/test_diligence_expected_risks.py tests/eval/test_eval_gate.py tests/adversarial/test_phase5_adversarial.py
uv run --extra dev python -m pytest tests/integration/test_phase2_walls.py tests/integration/test_api.py tests/integration/test_phase3_ui.py tests/unit/test_audit.py
uv run --extra dev ruff check .
npm run --silent fallow:dupes
uv run --extra dev mypy src/cite_or_die app
uv run --extra dev pyrefly check
test ! -f he-state.json || node "$HOME/.agents/scripts/he-state.mjs" validate he-state.json
```

## Traceability

| Requirement | Slice/task | Acceptance criteria | Verification |
|---|---|---|---|
| Ingest deal-room documents and structured client data | S2, S3, S4 | Source records classify by document type/workstream with metadata | API/flow integration tests and E2E workflow |
| Extract and normalise key data points | S5 | Facts and metrics require evidence and confidence | Extraction and normalisation tests |
| Flag and prioritise risks | S6 | Findings include severity, materiality, owner/status where available, and evidence | Risk unit tests, API/flow integration tests, expected-risk eval |
| Cross-reference workstreams | S7 | Insights link multiple workstreams and evidence | Flow integration test and E2E workflow |
| Accelerate reporting | S8 | Drafts are cited and review-needed | Model/repository tests, API/flow integration tests, E2E workflow |
| Audit and govern | S9 | Confidence, review status, escalation defaults, audit redaction | Isolation/audit integration test and existing audit/adversarial tests |
| Expected outputs | S3-S8 | Knowledge base, register, outputs, insight layer exist | Integration flow and E2E |
| Existing trust core preserved | All slices | Existing isolation, citation, audit, guardrail tests pass | Existing test suite subset plus gates |

## High-Risk Controls

- Tenant/matter/deal isolation: every repository method filters by tenant, matter, and deal in the same query; tests attempt cross-scope reads and updates.
- Model provider minimisation: the baseline diligence run does not call hosted providers; optional provider-assisted review must use scoped evidence context, prompt-injection checks, audit minimisation, and citation verification.
- Audit minimisation: `ALLOWED_AUDIT_KEYS` includes only IDs/statuses/counts for diligence; do not log raw prompts, source text, vendor response text, report prose, or full extracted clauses.
- Human review: `ReviewStatus` defaults to `needs_review`; mutation endpoints for review transitions are not implemented in this tracer.
- Hosted model boundary: keep production hosted-provider block; surface disabled state in the UI when relevant.
- Prompt-injection boundary: existing chat path scans user text and retrieved chunks before model calls; diligence currently does not send chunks to a model.
- Schema/state changes: the tracer creates SQLite tables lazily with `CREATE TABLE IF NOT EXISTS`; future migrations need explicit migration notes and rollback plan.
- UI split: diligence UI lives in `diligence.js` and `diligence.css` with a narrow `app.js` integration.

## Risks

- Data model breadth may sprawl. Mitigation: start with a tracer slice and typed models, then add fields only when tied to an acceptance test.
- Extraction accuracy can be overstated. Mitigation: confidence, evidence links, review state, and refusals for uncited claims.
- Cross-workstream insights can become vague. Mitigation: require linked facts/findings from at least two workstreams plus evidence.
- Report drafts can look too final. Mitigation: visible draft/review-needed state and no final sign-off language.
- UI density can hurt accessibility. Mitigation: token owner, WCAG 2.1 AA target, keyboard/focus tests, desktop/mobile E2E.

## Unknowns

None blocking the implemented tracer. Future expansion still needs product decisions for review mutation endpoints, production migration strategy, provider-assisted extraction, and real client data handling.

## Artifact Choice

Use both PRD and vertical-slice content in this single `plan.md`. External tracker issue creation is out of scope unless explicitly requested later.

## Next

Potential follow-up slices:

- Add read/list endpoints for deal sources, extracted facts, information requests, and cross-workstream insights if external clients need them outside the current UI run response.
- Add review mutation endpoints for findings, insights, information requests, and report drafts.
- Add explicit migrations before changing the diligence SQLite schema.
- Expand provider assistance into extraction only with scoped evidence context, prompt-injection checks, audit minimisation, and deterministic eval coverage.
