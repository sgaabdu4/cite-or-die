# Changelog

## 1.0.0

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
- Phase 5 adversarial hardening adds generated PDF attack fixtures, Garak/PyRIT-style probes, weekly security workflow, and a 70% mutation kill-rate gate.
- Phase 6 citation-graph retrieval adds NetworkX reference indexing, personalized PageRank, and a graph recall-lift eval gate.
- Phase 7 distribution readiness adds v1.0.0 version checks, package/Docker build targets, release workflow, and docs-site workflow/content.
- Phase 7 release compliance adds dependency CVE scanning, CycloneDX SBOM generation, and an internal security test report.
- Documentation and runtime privacy hardening clarify hosted-model data transfer, block hosted providers in production without explicit acknowledgement, disable the development token helper in production, and move Grafana's default admin password to a generated Docker secret.
