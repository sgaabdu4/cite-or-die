# Security Policy

Report security issues privately to the repository owner. Do not open public issues for vulnerabilities.

## Current Guarantees

- Raw prompts, raw document text, and raw model outputs are not written to audit logs by default.
- Tenants are checked at authorization time and retrieval time.
- Hosted providers receive only the retrieved top-k chunks, not full documents.
- Docker production mode supports secrets through files mounted at `/run/secrets`.

## Not Yet Guaranteed

- This repository has not completed an external security audit.
- The default development token endpoint is disabled only when `CITE_OR_DIE_APP_ENV=prod`.
- Local model dependencies are optional and must be separately reviewed before production use.
