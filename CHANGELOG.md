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
