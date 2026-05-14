# Changelog

## 0.1.0

- Initial local/server implementation.
- FastAPI upload and chat endpoints.
- Tenant-scoped retrieval with dense hash vectors, BM25, and RRF.
- FakeLLM, OpenAI, Anthropic, and Ollama provider adapters.
- Verbatim citation verification.
- JWT auth, tenant authorization, and append-only audit hash chain.
- Docker Compose stack with Qdrant, Caddy, Prometheus, Loki, Tempo, and Grafana.
- Phase 0 Tesla corpus seeding, `app.main:app` compatibility entrypoint, and `make e2e-local` smoke target.
- Phase 1 hybrid retrieval reranking, bundled 100-row T2-RAGBench eval gate, and CI eval target.
- Phase 1 lift gate documents BM25@1 and BM25@8 baselines separately.
- Phase 2 matter-scoped retrieval/context/output walls, Casbin ABAC, Presidio PII redaction, persisted PII entity maps, tamper exceptions, and input/retrieved-context guard gates.
- Phase 3 vanilla UI adds SSE chat, source uploads, matter document list, citation chips, and PDF.js page jumps.
- Phase 4a infrastructure adds the base Docker stack, Caddy TLS headers, SOPS+age encrypted env workflow, provider smoke checks, and install script.
- Phase 4b observability adds OpenTelemetry Collector, Prometheus alerts, Loki, Tempo, Grafana dashboards, token/audit metrics, and PII allowlist tracing.
