# cite-or-die

Privacy-first RAG with verbatim-verified citations and tenant-isolated retrieval.

## What It Does

- Upload PDF, DOCX, TXT, or Markdown documents.
- Store chunks locally under a tenant boundary.
- Retrieve with dense vectors plus BM25 sparse ranking and reciprocal-rank fusion.
- Send only top-k retrieved chunks to the selected LLM provider.
- Require structured model output.
- Reject or repair answers whose citations are not verbatim substrings of retrieved chunks.
- Keep an append-only hash-chain audit log with allowlisted fields only.
- Run locally with FakeLLM, or on a server with Docker, Qdrant, Caddy, and observability.

## Local Quick Start

```bash
uv sync --extra dev
cp .env.example .env
uv run cite-or-die serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`.

The default stack uses:

- `CITE_OR_DIE_LLM_PROVIDER=fake`
- `CITE_OR_DIE_VECTOR_BACKEND=memory`
- deterministic hash embeddings

That mode is designed for reproducible local tests and demos.

## CLI Smoke Test

```bash
uv run cite-or-die ingest examples/sample.txt
uv run cite-or-die chat "What does the sample say?"
```

## Server Run

Create the Docker secret file:

```bash
mkdir -p secrets
openssl rand -hex 32 > secrets/auth_secret.txt
docker compose up --build
```

Then visit:

- App: `https://cite-or-die.localhost`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

The compose stack includes the app, Qdrant, Caddy, OpenTelemetry Collector, Prometheus, Loki, Tempo, and Grafana.

## Provider Modes

```bash
CITE_OR_DIE_LLM_PROVIDER=fake
CITE_OR_DIE_LLM_PROVIDER=openai
CITE_OR_DIE_LLM_PROVIDER=anthropic
CITE_OR_DIE_LLM_PROVIDER=ollama
```

For hosted providers, set the matching secret through environment variables in development or Docker secrets/SOPS in production.

## Security Model

The system enforces three boundaries:

1. Retrieval boundary: each tenant has an isolated corpus and vector collection.
2. Context boundary: only top-k chunks are placed into the provider prompt.
3. Output boundary: chunk IDs and quotes must verify against retrieved chunks.

Audit logs use an allowlist. Raw prompts, raw document text, and raw model outputs are not logged by default.

## Test Gates

```bash
uv run ruff check .
uv run mypy src/cite_or_die
uv run pytest
```

Load test:

```bash
uv run locust -f tests/load/locustfile.py --host http://127.0.0.1:8765
```

## Production Notes

- Replace the development auth secret before deployment.
- Use Docker secrets or SOPS+age for provider keys.
- Start with FakeLLM in staging, then enable one hosted or local provider.
- Keep `CITE_OR_DIE_EMBEDDING_PROVIDER=hash` for lightweight smoke tests.
- Use `CITE_OR_DIE_EMBEDDING_PROVIDER=bge-m3` only after installing `uv sync --extra local-models`.
- Do not publish images or packages until release credentials and versioning are reviewed.
