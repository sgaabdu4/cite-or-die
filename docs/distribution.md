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
