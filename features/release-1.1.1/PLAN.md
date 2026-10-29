# Release 1.1.1 with patched dependencies

Status: Complete

## Outcome + scope

Prepare version 1.1.1 so the next manual release ships the aiohttp fix, and move the development-only msgpack lock past its memory leak advisory. Publishing the release is out of scope.

## Repository context

Owners: pyproject.toml, src/cite_or_die/__init__.py, docker-compose.yml, scripts/release_check.py, Makefile, CHANGELOG.md, .github/workflows/release.yml and uv.lock.
Same cause: The aiohttp bump landed in #13 and needs a release to reach users. msgpack 1.2.1 (GHSA-j586-36cw-2gc2, fixed in 1.2.3) arrives only through the dev extra via locust and pip-audit's cachecontrol; no other lock in the repository resolves msgpack.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked for every OSV finding fixed, branches rebased on main and merged where needed. The personal one-PR rule puts the msgpack bump into the open release PR. The release workflow keeps main's branch guard, read-only permissions, concurrency and environment; only its version moves to 1.1.1.

## Acceptance + steps

- [x] Every version source reads 1.1.1 and the release guard accepts only 1.1.1 on main. N/A — `scripts/release_check.py` in the native gate checks the version sources.
- [x] msgpack resolves at 1.2.4 and OSV reports no findings for uv.lock. N/A — lock resolution and the gate's vulnerability scan verify dependency metadata.
- [x] Existing tests and required gates pass unchanged. N/A — the full native gate runs the configured check inventory.

## Baseline + execution

Result: Passed
Evidence: Before the change, OSV reported msgpack 1.2.1 (GHSA-j586-36cw-2gc2) in uv.lock on main. The release branch was rebased on main; the only conflict was the release workflow guard, resolved by keeping main's guard with version 1.1.1. `uv lock --check` passed and `uv lock --upgrade-package msgpack` moved msgpack from 1.2.1 to 1.2.4.
Execution: One owner rebases, bumps the lock and runs the full native gate.

## Risks + recovery

msgpack is used only by development tools, so application behavior cannot change. Merging does not publish; the release workflow needs a manual dispatch. Reverting the PR restores the prior lock and version.

## ux_reference

N/A — version and dependency lock changes have no interface.

## Verification

Result: Passed
Evidence: The full native gate (`python3 .hooks/hard-eng.py check --base origin/main`) passed on this branch, including tests, release checks and the vulnerability scan of uv.lock.
E2E: N/A — no runtime behavior changes; the existing suites run in the gate.

Delivery target: Merge
Delivery: Pending — required pull request checks and merge.
