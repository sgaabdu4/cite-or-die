# Contributing

Run the full local gate before opening a pull request:

```bash
make setup
uv run ruff check .
npm run --silent fallow:dupes
uv run mypy src/cite_or_die app
uv run pytest
```

`make setup` installs npm tooling and configures `.githooks/pre-push`.

Changes that touch retrieval, providers, guardrails, tenancy, diligence scope, or audit logging need tests for the failure path as well as the happy path.
