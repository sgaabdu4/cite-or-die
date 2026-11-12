# Bring every direct and dev package to its newest release

Status: Complete

## Outcome + scope

Every direct and dev dependency of the root Python project and of `scripts/record_demo` moves to its newest stable release that is at least two days old, so the `freshness` gate passes. Non-goals: other behavior changes and releases younger than two days.

## Repository context

Owners: `pyproject.toml` and `uv.lock` for Python; `scripts/record_demo/package.json` and `bun.lock` for the demo recorder. The `freshness` gate in `hard-eng.gates.json` lists the old packages.
Same cause: N/A — the packages were not updated for some weeks; one change per package group removes every stale entry.
Single source: N/A — no rule, value or type is added or copied.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner asked for the freshness gate to pass on this repository; the one-PR rule puts all updates in one branch.

## Acceptance + steps

- [x] Qdrant search returns the nearest chunk first after the qdrant-client update removed `search`. `tests/unit/test_vector_store.py::test_qdrant_store_returns_the_nearest_chunk_first` passes.
- [x] The rest of the suite stays green on the new versions. N/A — the `tests` gates of both packages run every existing test and are the proof.
- [x] Types and style stay clean on the new type checkers and linter. N/A — the `types`, `lint`, `format` and `annotations` gates are the proof.
- [x] Each `freshness` gate reports no stale package. N/A — the `freshness` gates are the proof.

## Baseline + execution

Result: Passed
Evidence: Before: `uv tree --outdated` and `bun outdated` listed about 40 packages behind. After: both list only releases younger than two days.
Execution: One commit per package group (web stack, runtime libraries, PDF libraries, test tools, ruff, type checkers, transformers, playwright), the suite run after each group. One code repair: `QdrantVectorStore.search` calls `query_points`.

## Risks + recovery

Risk: major updates (pypdf 7, rich 15, typer 0.29, mypy 2) can change behavior outside the tests; the Qdrant path has no test against a live server. Recovery: revert the group commit that caused it.

## ux_reference

N/A — dependency updates only; no visible surface.

## Verification

Result: Passed
Evidence: The Complete check passes every gate; the Python suite passes after each group.
E2E: N/A — no user journey changes.
Retro: The types gate found the removed Qdrant `search` call, which no test reached → `tests/unit/test_vector_store.py::test_qdrant_store_returns_the_nearest_chunk_first`. The plan check refused my first plan twice for format → None — the check caught both at once and the plan is fixed.
Delivery target: Merge
Delivery: Pending — the pull request checks, then the merge.
