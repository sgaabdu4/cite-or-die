# E2E Flows

## Diligence Workflow

- Target: local test server at `http://127.0.0.1:8765`
- Preconditions: local test server running with `CITE_OR_DIE_APP_ENV=test`; root Node tooling installed with `npm ci --ignore-scripts` and `npm run --silent e2e:install-browsers`
- Steps: configure the Offline demo provider, upload six deal files, select all files, ask a cited question, create the review, run the accelerator, inspect every output tab, open cited evidence, run and rerun the AI-assisted review, rerun the accelerator
- Automation command: `E2E_BASE_URL=http://127.0.0.1:8765 npm run --silent e2e:diligence`
- Expected result: uploaded files are scoped, cited questions work, evidence-backed risks, insights, baseline report drafts, and AI-assisted report draft render with review state and clickable source evidence
- Evidence needed: `events.jsonl`, screenshots, desktop/mobile videos, logs

## Risky Writes

- Local test uploads and local SQLite writes only.
- Timestamped evidence folders under `docs/e2e/<RUN_ID>/` are ignored when the
  run ID starts with digits.
- No delete, payment, email/SMS, sharing, or production actions.
