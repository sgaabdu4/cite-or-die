# E2E Automation

Every persisted E2E flow needs a runnable automation command.
Manual exploration can discover a flow, but the final project pack should leave an executable command for the next AI or engineer.

## Commands

- Start local test server:
  `CITE_OR_DIE_APP_ENV=test CITE_OR_DIE_DATA_DIR=/tmp/cite-or-die-e2e CITE_OR_DIE_AUTH_SECRET=test-secret-with-at-least-32-bytes uv run --extra dev uvicorn cite_or_die.api.app:app --host 127.0.0.1 --port 8765`
- Install Node tooling:
  `npm ci --ignore-scripts`
- Install the project-managed Playwright browser:
  `npm run --silent e2e:install-browsers`
- Run diligence workflow:
  `E2E_BASE_URL=http://127.0.0.1:8765 npm run --silent e2e:diligence`

The runner uploads fixture files through the UI and writes timestamped evidence
under `docs/e2e/<RUN_ID>/`; numeric run IDs are ignored by `.gitignore`.

## Rules

- Prefer existing project runners when they exist
- Add the smallest durable automated smoke when no runner exists
- Do not commit cookies, tokens, passwords, private session dumps, or real customer data
- Do not count unit tests, typechecks, static scans, or curl-only checks as E2E
