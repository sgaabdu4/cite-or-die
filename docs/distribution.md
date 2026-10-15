# Distribution

Release readiness is local until the release workflow is explicitly run.

- Package name: `cite-or-die`
- Docker image: `sgaabdu4/cite-or-die`
- Release version: `1.1.0`
- Security gate: `make release-security`
- SBOM artifact: `dist/security/cite-or-die-1.1.0.cdx.json`
- Local package gate: `make build-dist`
- Local Docker gate: `make docker-build`
- Publish gate: GitHub Actions `Release` workflow with confirmation input `ship it`

The release workflow publishes only from a manual workflow dispatch. It does not run from a normal push or PR.

## Required publish setup

The release workflow already has the publish steps, but PyPI and Docker Hub still need credentials
or trusted publishing configured outside the repo.

GitHub secrets path:

```bash
gh secret set UV_PUBLISH_TOKEN --repo sgaabdu4/cite-or-die
gh secret set DOCKERHUB_USERNAME --repo sgaabdu4/cite-or-die --body sgaabdu4
gh secret set DOCKERHUB_TOKEN --repo sgaabdu4/cite-or-die
gh workflow run Release --repo sgaabdu4/cite-or-die -f confirm='ship it' -f version='1.1.0'
```

PyPI trusted publishing path:

- Owner/repo: `sgaabdu4/cite-or-die`
- Workflow: `.github/workflows/release.yml`
- Branch: `main`
- Environment: none

Verification after publish:

```bash
curl -fsS https://pypi.org/pypi/cite-or-die/json
docker manifest inspect sgaabdu4/cite-or-die:1.1.0
```

## Runtime deployment choices

Docker can run on the same laptop used for development or on a server:

```bash
./install.sh && docker compose up --build
```

The Docker stack runs the app with `CITE_OR_DIE_APP_ENV=prod`, disables the
development token helper, reads app/provider secrets from `secrets/*.txt`, and
uses a generated Grafana admin password from `secrets/grafana_admin_password.txt`.

With Qdrant enabled, vector collections are keyed by tenant, matter, and
embedding profile. Same-dimensional legacy tenant/matter collections are copied
into the profile-specific collection automatically when first used.

Use `CITE_OR_DIE_LLM_PROVIDER=ollama` for local models served by Ollama, including Qwen and
DeepSeek model tags you have pulled locally:

```bash
ollama pull qwen3:8b
CITE_OR_DIE_LLM_PROVIDER=ollama CITE_OR_DIE_LLM_MODEL=qwen3:8b CITE_OR_DIE_OLLAMA_BASE_URL=http://localhost:11434 uv run cite-or-die serve --host 127.0.0.1 --port 8765
```

When Docker needs to reach a host machine provider through
`host.docker.internal`, include `host.docker.internal` in
`CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS` as in `docker-compose.yml`.

Use `CITE_OR_DIE_LLM_PROVIDER=openai-compatible` for hosted providers that expose
OpenAI-compatible chat completions:

| Provider | Base URL | `CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS` |
| --- | --- | --- |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `generativelanguage.googleapis.com` |
| DeepSeek | `https://api.deepseek.com` | `api.deepseek.com` |
| Kimi/Moonshot | `https://api.moonshot.ai/v1` | `api.moonshot.ai` |
| Hugging Face Inference Providers | `https://router.huggingface.co/v1` | `router.huggingface.co` |
| Alibaba Qwen DashScope, Singapore | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | `dashscope-intl.aliyuncs.com` |

Source pages checked with Tavily: Google Gemini OpenAI compatibility docs,
DeepSeek API docs, Kimi API Platform migration guide, Hugging Face Inference
Providers chat completion docs, Ollama API docs, and Alibaba Cloud Model Studio
OpenAI-compatible chat docs.

```bash
CITE_OR_DIE_LLM_PROVIDER=openai-compatible CITE_OR_DIE_OPENAI_COMPATIBLE_BASE_URL=<base-url> CITE_OR_DIE_PROVIDER_BASE_URL_ALLOWED_HOSTS=<host> CITE_OR_DIE_OPENAI_COMPATIBLE_API_KEY=<key> CITE_OR_DIE_LLM_MODEL=<model> uv run cite-or-die serve --host 127.0.0.1 --port 8765
```

Hosted providers receive the question and retrieved chat chunks, or the
AI-assisted diligence prompt and cited evidence chunks. In production,
set `CITE_OR_DIE_ALLOW_HOSTED_LLM=true` only after the operator accepts that
data transfer.
