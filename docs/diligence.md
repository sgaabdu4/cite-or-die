# Diligence Accelerator

The diligence accelerator is the current deal-workflow layer on top of the
existing cite-or-die evidence core. It uses uploaded matter documents, stores
deal objects by tenant, matter, and deal, and keeps every generated fact,
finding, insight, and report claim linked to source evidence.

The implemented tracer is local and deterministic. `POST /diligence/deals/{deal_id}/run`
does not call a hosted model provider; it reads already-ingested chunks from the
active tenant and matter, applies extraction/risk rules, and stores review-ready
outputs. Chat still uses the configured provider path described in `README.md`.

## UI Workflow

1. Open the app with the intended tenant and matter selected.
2. Click **Load sample deal room** in the diligence workspace. This uploads six
   safe text sources, creates `Project Northstar`, and classifies its sources.
   Alternatively, select existing matter sources and click
   **Review selected sources** to create a scoped review.
3. Click **Run diligence review** to build the knowledge base, risk register,
   cross-workstream insights, information-request tracker, and report drafts.
4. Use the Source library, Extraction review, Risk register,
   Cross-workstream insights, IR tracker, and Report drafts tabs.
5. Click evidence buttons to open the existing citation drawer at the source
   quote.

Changing workspace tenant or matter resets the diligence UI state so outputs do
not carry across scopes.

## API Surface

All diligence routes require the same bearer token model as the rest of the API.
Create/classify/run operations require an authenticated role with `upload`
permission for the active tenant and matter. Read routes require `read`.

| Method | Route | Behavior |
| --- | --- | --- |
| `POST` | `/diligence/deals` | Creates a deal in the active tenant and matter. |
| `POST` | `/diligence/deals/{deal_id}/sources/classify` | Classifies the deal's source documents by document type, workstream, and confidence. |
| `POST` | `/diligence/deals/{deal_id}/run` | Classifies sources when needed, extracts facts, creates findings, builds insights, drafts reports, stores outputs, and returns the run result. |
| `GET` | `/diligence/deals/{deal_id}/findings` | Returns stored findings for the deal. |
| `GET` | `/diligence/deals/{deal_id}/reports` | Returns stored report drafts for the deal. |

`POST /diligence/deals` accepts:

```json
{
  "name": "Project Northstar",
  "target_business": "Northstar Managed Services",
  "target_revenue_gbp_m": 180,
  "horizon_weeks": 6,
  "source_doc_ids": []
}
```

`target_revenue_gbp_m` must be 100-250, `horizon_weeks` must be 4-8, and
`source_doc_ids` is optional with a maximum of 50 IDs. When omitted or empty,
each accelerator run refreshes the source set from all documents in the current
matter. Explicit source IDs are de-duplicated, must already belong to the active
tenant and matter, and stay scoped to those selected documents.

`POST /diligence/deals/{deal_id}/run` returns a `DiligenceRunResult` with the
deal, `knowledge_base`, `findings`, `insights`, `report_drafts`, and metrics for
source, fact, finding, insight, and report counts plus `horizon_weeks`.

## Stored Objects

`DiligenceRepository` creates these SQLite tables in the configured
`sqlite_path`:

- `diligence_deals`
- `diligence_sources`
- `diligence_facts`
- `diligence_information_requests`
- `diligence_vendor_responses`
- `diligence_findings`
- `diligence_insights`
- `diligence_reports`

Every table is queried with tenant and matter scope; deal-specific tables also
filter by `deal_id`. Output replacement validates that each item matches the
target tenant, matter, and deal before writing.

## Current Extraction And Risk Rules

Source classification uses filename, content type, and up to 4,000 characters of
sample text. It recognizes contracts, financial packs, customer data, HR records,
operational reports, org charts, management presentations, Q&A logs, information
requests, vendor responses, deal precedents, comparable transactions, sector
benchmarks, public market information, and unknown sources.

Extraction currently recognizes evidence-backed:

- revenue, reported EBITDA, EBITDA normalisation add-backs, and recurring
  restructuring costs;
- top-customer revenue share and churn;
- utilisation, SLA backlog, employee count, and attrition;
- change-of-control consent requirements;
- termination-for-convenience notice periods;
- delayed open information requests and vendor responses.

Risk findings are created for:

- `customer_concentration`: top-customer concentration at or above 30 percent;
- `earnings_normalisation`: earnings normalisation overlap with recurring
  restructuring cost;
- `contract_consent`: required change-of-control consent;
- `non_standard_clause`: termination-for-convenience notice of 30 days or less;
- `open_information_request`: delayed open information requests.

Report drafts are first drafts only. They default to `needs_review` and include
cited claims from stored findings.

## Audit And Governance

Diligence writes `AuditEventType.diligence` rows with allowlisted metadata only:
`deal_id`, `matter_id`, `status`, and source/fact/finding/insight/report counts.
Raw source text, extracted fact values, finding prose, report prose, and vendor
response text are not audit payload fields. Audit appends use serialized SQLite
writes so concurrent diligence events preserve the hash chain.

## Verification

Focused checks:

```bash
uv run --extra dev python -m pytest tests/unit/test_diligence_models.py tests/unit/test_diligence_classification.py tests/unit/test_diligence_extraction.py tests/unit/test_diligence_risk.py tests/unit/test_diligence_repository.py
uv run --extra dev python -m pytest tests/integration/test_diligence_api.py tests/integration/test_diligence_flow.py tests/integration/test_diligence_isolation.py tests/integration/test_diligence_ui.py
uv run --extra dev python -m pytest tests/eval/test_diligence_expected_risks.py
node --check src/cite_or_die/ui/diligence.js
```

Browser proof is documented in `docs/e2e/` and run with
`tests/e2e/diligence_workflow.mjs` against a local test server.
