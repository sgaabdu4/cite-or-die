# Contributing

Run the full local gate before opening a pull request:

```bash
uv run ruff check .
uv run mypy src/cite_or_die
uv run pytest
```

Changes that touch retrieval, providers, guardrails, tenancy, or audit logging need tests for the failure path as well as the happy path.
