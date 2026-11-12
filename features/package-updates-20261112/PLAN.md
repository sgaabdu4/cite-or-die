# Bring every direct and dev package to its newest release

Status: Complete

## Outcome + scope

Every direct and dev dependency of the root Python project and of `scripts/record_demo` moves to its newest stable release that is at least two days old, so the `freshness` gate passes. The 18 old `security` findings (hot-path rules) are repaired so the Complete check passes. Non-goals: other behavior changes and releases younger than two days.

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
- [x] Two constant Python patterns compile once at module level. `tests/unit/test_vector_store.py::test_collection_name_replaces_unsafe_characters` passes; the `security` gate reports no `regex-built-in-function-python`.
- [x] The UI scripts build their constant patterns once. N/A — the repository has no JavaScript test for the UI scripts; a before and after run of `locateTextQuote` and `locateQuoteSegments` printed the same result, and the `security` gate is the proof.
- [x] Audit and repository reads select named columns and return the same fields. `tests/unit/test_repository.py::test_repository_lists_return_every_stored_field` and `tests/unit/test_repository.py::test_audit_recent_returns_every_column_newest_first` pass.
- [x] Settings are built once at app start and read from the app state. `tests/integration/test_api.py::test_dev_token_endpoint_is_not_available_in_prod` passes.
- [x] The guard scanner loads once when the service starts and the scans use it. `tests/integration/test_service.py::test_chat_uses_the_service_guard_scanner` and `tests/unit/test_model_guard.py::test_enabled_model_guard_does_not_silently_fall_back` pass.
- [x] The cursor glide runs its mouse moves in order. `scripts/record_demo/tests/record.test.ts::inOrder finishes each step before it starts the next` passes, and the recording journey test still passes.

## Baseline + execution

Result: Passed
Evidence: Before: `uv tree --outdated` and `bun outdated` listed about 40 packages behind. After: both list only releases younger than two days.
Execution: One commit per package group (web stack, runtime libraries, PDF libraries, test tools, ruff, type checkers, transformers, playwright), the suite run after each group. One code repair: `QdrantVectorStore.search` calls `query_points`. Then one commit per security concern: regex (Python, JavaScript), named SQL columns, settings, guard scanner, ordered glide.

## Risks + recovery

Risk: the guard models now load when the service starts, not at the first request, and only when `CITE_OR_DIE_ENABLE_LLM_GUARD_MODELS=1`. Major updates (pypdf 7, rich 15, typer 0.29, mypy 2) can change behavior outside the tests; the Qdrant path has no test against a live server. Recovery: revert the group commit that caused it.

## ux_reference

N/A — dependency updates only; no visible surface.

## Verification

Result: Passed
Evidence: The Complete check passes every gate; the Python suite passes after each group.
E2E: N/A — no user journey changes.
Retro: The types gate found the removed Qdrant `search` call, which no test reached → `tests/unit/test_vector_store.py::test_qdrant_store_returns_the_nearest_chunk_first`. The plan check refused my first plan twice for format → None — the check caught both at once and the plan is fixed.
Delivery target: Merge
Delivery: Pending — the pull request checks, then the merge.
