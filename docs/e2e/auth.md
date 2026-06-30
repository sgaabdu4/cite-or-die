# E2E Auth

Do not store secrets here.

## Login

- Method: development token helper
- Test account owner: local test tenant
- Roles: admin via `/dev/token`
- Safe seeded data: synthetic deal-room sources in `tests/e2e/diligence_workflow.mjs`
- Data mode: seeded-test

## Saved State

- State path: none
- Created by: not applicable
- Refresh rule: each run requests a new local development token

Only reference safe local state paths.
Do not commit cookies, tokens, passwords, or private session dumps.
