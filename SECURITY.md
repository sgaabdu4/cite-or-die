# Security Policy

Report security issues privately to the repository owner. Do not open public issues for vulnerabilities.

## Current Guarantees

- Raw prompts, raw document text, and raw model outputs are not written to audit logs by default.
- Tenants are checked at authorization time and retrieval time.
- Diligence deals, sources, facts, findings, insights, and reports are stored and read by tenant, matter, and deal scope.
- Diligence audit events store only allowlisted IDs, statuses, and counts.
- Hosted providers receive only the retrieved top-k chunks, not full documents.
- The current diligence accelerator run does not call hosted providers; it uses local rules over already-ingested chunks.
- Hosted providers are blocked in production unless
  `CITE_OR_DIE_ALLOW_HOSTED_LLM=true` is set.
- Docker production mode supports secrets through files mounted at `/run/secrets`.
- SOPS+age keeps the committed `secrets.enc.env` encrypted; decrypted env files stay ignored.

## Not Yet Guaranteed

- This repository has not completed an external security audit.
- The app has bearer-token auth, but no built-in user login, SSO, SAML, OIDC, or user admin UI.
- Local model dependencies are optional and must be separately reviewed before production use.
- Retrieved chunks can still contain sensitive client facts. Use local models when those facts must not leave your machine or server.
- Diligence report drafts are review-needed working output, not final deal advice or sign-off.
