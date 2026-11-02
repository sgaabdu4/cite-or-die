# Fix the November pypdf advisories

Status: Complete

## Outcome + scope

pypdf moves from 6.21.2 to 6.21.4, the release that fixes the seven advisories published after 6.21.2. Non-goals: other dependencies and application code.

## Repository context

Owners: `pyproject.toml` pins `pypdf==6.21.2` and `uv.lock` records it. The Hard Eng update's pre-push ran `vulnerabilities` (OSV) and `legacy-security` (pip-audit); both failed on pypdf 6.21.2 with fixes in 6.21.3 and 6.21.4.
Same cause: N/A — pypdf is the only package either scanner reported.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner gave full authority on 2026-10-31 to finish the Hard Eng update in every repository. The one-PR rule puts this fix in the update PR.

## Acceptance + steps

- [x] OSV and pip-audit report no vulnerable packages. N/A — the scanners read the lock, so the `vulnerabilities` and `legacy-security` gates are the proof.
- [x] PDF ingestion keeps working on the patch release. N/A — the full Python suite, which parses PDFs, runs in the pre-push gate.

## Baseline + execution

Result: Passed
Evidence: Before: OSV listed seven pypdf 6.21.2 advisories and pip-audit exited 1 with fixes in 6.21.3 and 6.21.4. After: `uv lock --upgrade-package pypdf` resolved 226 packages with pypdf 6.21.4.
Execution: One change: the exact pin and the lock move to 6.21.4.

## Risks + recovery

Risk: a patch release could change PDF parsing; the full suite covers it. Recovery: revert this commit.

## ux_reference

N/A — dependency patch only; no visible surface.

## Verification

Result: Passed
Evidence: the Hard Eng pre-push gate runs both scanners and the full suite on this commit.
E2E: N/A — dependency patch only; no user journey changes.
Delivery target: Merge
Delivery: Pending — the Hard Eng update PR checks, then the merge.
