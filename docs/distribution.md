# Distribution

Release readiness is local until the release workflow is explicitly run.

- Package name: `cite-or-die`
- Docker image: `sgaabdu4/cite-or-die`
- Release version: `1.0.0`
- Security gate: `make release-security`
- SBOM artifact: `dist/security/cite-or-die-1.0.0.cdx.json`
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
gh workflow run Release --repo sgaabdu4/cite-or-die -f confirm='ship it' -f version='1.0.0'
```

PyPI trusted publishing path:

- Owner/repo: `sgaabdu4/cite-or-die`
- Workflow: `.github/workflows/release.yml`
- Branch: `main`
- Environment: none

Verification after publish:

```bash
curl -fsS https://pypi.org/pypi/cite-or-die/json
docker manifest inspect sgaabdu4/cite-or-die:1.0.0
```
