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
./install.sh
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

## Phase 0 Local E2E

```bash
make seed-tesla
uv run uvicorn app.main:app --port 8765
```

Then run the smoke query from another shell:

```bash
curl -s http://localhost:8765/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"customer concentration?","matter_id":"m_default","session_id":"00000000-0000-0000-0000-000000000001","stream":false}' \
  | jq -e '.citations[0].text_excerpt and (.citation_valid_count > 0)'
```

`make e2e-local` downloads the Tesla SEC filing if needed, seeds it, and runs the local unit, integration, and eval tests.

## Phase 1 Retrieval Eval

```bash
make eval-t2ragbench-100
```

The bundled 100-row T2-RAGBench subset checks `recall_at_8 >= 0.80`, `faithfulness >= 0.85`, `citation_valid >= 0.95`, and `hybrid_lift_over_bm25 >= 0.15`. The lift gate compares hybrid recall@8 to BM25-only recall@1; BM25@8 lift is reported separately as `hybrid_lift_over_bm25_at_8`. Regenerate the subset with `make download-t2ragbench-subset`. The default local reranker is deterministic and lexical; set `CITE_OR_DIE_RERANKER_PROVIDER=bge-reranker-v2-m3` after installing `uv sync --extra local-models` to use the BGE cross-encoder.

## Server Run

Create local Docker secret files:

```bash
./install.sh
docker compose up --build
```

Then visit:

- App: `https://cite-or-die.localhost`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

The compose stack includes app, Qdrant, Postgres, Redis, Caddy, OpenTelemetry Collector, Prometheus, Loki, Tempo, and Grafana.

## Phase 3 UI

The root page serves the vanilla HTML/CSS/JS workspace. Uploads stay in the selected tenant and matter, `/chat/stream` returns `text/event-stream`, and citation chips open `/docs/{doc_id}/file`; PDF sources render through PDF.js and jump to the cited page.

## Provider Modes

```bash
CITE_OR_DIE_LLM_PROVIDER=fake
CITE_OR_DIE_LLM_PROVIDER=openai
CITE_OR_DIE_LLM_PROVIDER=anthropic
CITE_OR_DIE_LLM_PROVIDER=ollama
```

For hosted providers, set the matching secret through environment variables in development or Docker secrets/SOPS in production.

Provider smoke checks exercise the same service `/chat` path:

```bash
PROVIDER=fake make provider-smoke
PROVIDER=openai CITE_OR_DIE_LLM_MODEL=<model> CITE_OR_DIE_OPENAI_API_KEY=<key> make provider-smoke
PROVIDER=anthropic CITE_OR_DIE_LLM_MODEL=<model> CITE_OR_DIE_ANTHROPIC_API_KEY=<key> make provider-smoke
PROVIDER=ollama CITE_OR_DIE_LLM_MODEL=<model> CITE_OR_DIE_OLLAMA_BASE_URL=http://localhost:11434 make provider-smoke
```

## SOPS Secrets

`secrets.enc.env` is the committed encrypted environment template. Decrypt it on machines with the configured age identity:

```bash
SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt sops --decrypt secrets.enc.env > secrets.dec.env
```

`secrets.dec.env` stays ignored. Docker secrets live in `secrets/*.txt`; `./install.sh` creates local placeholder files for development.

## Observability

`/healthz`, `/readyz`, and `/metrics` are live in the app. The OpenTelemetry collector deletes high-risk attributes such as `query.text`, `doc.content`, `prompt`, and `response.body`, then applies an explicit span-attribute allowlist before exporting traces to Tempo. Prometheus loads `ops/prometheus/alerts.yml`, including the `FaithfulnessGateFailure` alert. Grafana provisions dashboards for RAG latency, token spend, and audit-event rate.

## Adversarial Hardening

`make adversarial` generates white-text, zero-width, homoglyph, RTL override, and template-injection PDF fixtures with reportlab, then verifies those payloads are rejected and audited. The same target runs local Garak/PyRIT-style probe adapters. `make mutation` runs the Phase 5 mutation gate and fails below a 70% kill rate.

## Citation Graph

Retrieval fuses dense vectors, BM25, and a NetworkX citation graph. The graph links adjacent chunks and shared legal references such as sections, covenants, and project names, then uses personalized PageRank as a third weighted RRF lane. `make eval-graph` checks the Phase 6 multi-hop recall lift gate.

## Distribution

`make release-check` verifies the package version, runtime `__version__`, and Docker Compose image tag are all `1.0.0`. `make release-security` runs the dependency CVE audit and writes a CycloneDX SBOM to `dist/security/`. `make build-dist` builds the PyPI artifacts into `dist/`, and `make docker-build` builds the local Docker image. The release workflow is manual and requires the `ship it` confirmation input before publishing.

## Security Model

The system enforces three boundaries:

1. Retrieval boundary: each tenant and matter has an isolated retrieval scope.
2. Context boundary: chat requests must stay bound to the authenticated matter.
3. Output boundary: chunk IDs and quotes must verify against retrieved chunks in the same matter.

Casbin enforces tenant, matter, role, and action ABAC before upload/read/chat. Presidio redacts PII before chunking and embedding, and the entity map is stored in local SQLite without raw PII values. Query and retrieved-context guardrails use local scanners by default; `CITE_OR_DIE_ENABLE_LLM_GUARD_MODELS=1` attempts to load an operator-installed LLM Guard stack when a compatible scanner package is present.

Audit logs use an allowlist. Raw prompts, raw document text, and raw model outputs are not logged by default.

## Test Gates

```bash
uv run ruff check .
uv run mypy src/cite_or_die app
uv run pytest
make eval-t2ragbench-100
make e2e-multitenant
uv run pytest tests/integration/test_phase3_ui.py
uv run pytest tests/unit/test_providers.py
uv run pytest tests/integration/test_phase4b_observability.py
make adversarial
make mutation
make eval-graph
make release-security
make release-check
make build-dist
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
- Do not publish images or packages until the release workflow is run with the `ship it` confirmation.
