# E2E Flows

## Diligence Workflow

- Target: local test server at `http://127.0.0.1:8765`
- Preconditions: local test server running with `CITE_OR_DIE_APP_ENV=test`
- Steps: load synthetic deal room, run accelerator, inspect risk register, open cross-workstream insights, open report drafts, open cited evidence
- Automation command: `NODE_PATH=$HOME/.cache/hard-eng/e2e-playwright/node_modules E2E_BASE_URL=http://127.0.0.1:8765 node tests/e2e/diligence_workflow.mjs`
- Expected result: evidence-backed risks, insights, and report draft render with review state and clickable source evidence
- Evidence needed: events row, screenshot/video timestamp, logs

## Risky Writes

- Local test uploads and local SQLite writes only.
- No delete, payment, email/SMS, sharing, or production actions.
