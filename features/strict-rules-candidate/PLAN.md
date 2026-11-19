# Strict rules candidate repair

Status: Complete

## Outcome + scope

The repository passes the Hard Eng release candidate. Ruff runs with its own default rules, with no `select`, `ignore` or `per-file-ignores`, and every finding is fixed in code. The `legacy-lint` gate runs the pinned Ruff. The outdated `httpx2` bound moves to 2.16.2 because the freshness gate runs once `pyproject.toml` changes. Non-goals: new features, other pins.

## Sources + coverage

Sources: N/A — the coordinator's request is the only source.
Deliverables: None

## Repository context

Owners:
- `pyproject.toml` owns the Ruff settings and the `httpx2` bound; `uv.lock` holds the resolved version.
- `hard-eng.gates.json` owns the `legacy-lint` command.
- `src/cite_or_die/api/app.py` and `src/cite_or_die/auth/jwt.py` own the FastAPI dependencies.

Same cause: the short `select` and the `ignore` lists were the only Ruff rule settings in the repository. The 31 findings that appeared are listed by rule in the PR.
Single source: the Ruff version lives in `uv.lock`; the `uvx` pin in the gate repeats it, because the gate may not use `uv run` for a dev extra.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous. The coordinator asked for this repository to pass the release candidate, delivered as an unmerged PR.

## Acceptance + steps

- [x] The default Ruff rules pass with no ignore → N/A — the lint gate is the proof.
- [x] FastAPI routes keep their dependencies and form fields → `tests/integration/test_api.py::test_api_upload_chat_flow` and `tests/integration/test_api.py::test_chat_stream_returns_error_event_for_generation_failure`
- [x] An unexpected chat failure sends a generic error event and no error text → `tests/integration/test_api.py::test_chat_stream_returns_error_event_for_generation_failure`
- [x] The legacy lint gate uses the Ruff the lock file pins → N/A — the candidate check is the proof.

## Baseline + execution

Result: Passed
Evidence: Starting code origin/main after the Hard Eng update. With the default rules `ruff check .` reports 31 findings (B008 21, BLE001 2, PYI063 2, TRY004 2, ISC004 1, PT014 1, EXE002 1, RUF007 1) and Ruff 0.17.5 adds one SIM102. The candidate check refuses the Ruff settings and the `legacy-lint` gate.
Execution: One agent; one commit per rule family.

## Risks + recovery

`pyproject.toml` and `uv.lock` change, so the Docker image builds with `httpx2` 2.16.2 after the merge. Two provider parse errors now raise `TypeError`, which no code catches by type. The chat stream catches HTTP, Qdrant, attribute, lookup, OS, runtime, type and value errors, logs only the error type and still sends the same error event; an error of another type now ends the stream. The readiness probe catches Qdrant API, Qdrant client and OS errors. Ruff's default set holds only the `S` rules S102, S110 and S112; the other `S` security rules are not in it, and the Semgrep gate still scans the code. Declined: keeping a longer Ruff `select` for the `S` family. The repository owner's rule is Ruff's own rule set with no `select`, and Semgrep covers the security checks. Recovery: revert the merge commit.

## ux_reference

N/A — no visual change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` exits 0 with 40 gates PASS. The same check in a sealed copy updated to Hard Eng develop c194bb73, with `--base` at the main tip, exits 0 with 40 gates PASS. The first sealed run failed freshness on `httpx2` and the performance benchmark; the benchmark compares two means and passed on the rerun.
E2E: N/A — no user journey changes.
Real service: N/A — no changed code calls an outside service.
Retro: Failed check: the Ruff settings refusal, the legacy-lint refusal and the freshness gate on `httpx2` → the settings are gone, the gate runs the pinned Ruff and the bound is 2.16.2 (the settings check and the freshness gate stay the prevention).

Delivery target: Merge
Delivery: Pending — PR, the coordinator merges, then confirm main CI passes.
