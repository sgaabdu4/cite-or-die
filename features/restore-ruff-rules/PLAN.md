# Restore the Ruff rules that the first repair dropped

Status: Complete

## Outcome + scope

Every Ruff rule that was on before the strict rules repair is on again. `extend-select` in `[tool.ruff.lint]` lists the families E, F, I, UP, B, ASYNC and every S rule except S101, which the project kept off before. No ignore key is added. The 12 findings that the restored rules report are fixed in code. Non-goals: other settings, other rules.

## Sources + coverage

Sources: N/A — the coordinator's audit is the only source.
Deliverables: None

## Repository context

Owners: `pyproject.toml` owns the Ruff settings. `src/cite_or_die/core/models.py` owns the three enums. `tests/` owns the test secrets.
Same cause: the earlier repair removed `select`, which also removed rules that the release does not refuse. Every Ruff gate in `hard-eng.gates.json` reads this file: `lint` and `legacy-lint` read it; `complexity` and `annotations` set their own rules. `legacy-lint` runs `uvx ruff@0.17.5`, the version in `uv.lock`.
Single source: the rule list lives only in `pyproject.toml`.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous. The coordinator asked for this follow-up repair.

## Acceptance + steps

- [x] No rule that was on before is off now → N/A — the before and after `--show-settings` rule sets are compared in the PR: 217 before, 499 after, 0 lost.
- [x] The three enums still serialize to the same values → `tests/integration/test_api.py::test_api_upload_chat_flow`
- [x] The secret tests still pass with run-time values → `tests/unit/test_runtime_config.py::test_wrong_secret_silently_fails_decrypt`

## Baseline + execution

Result: Passed
Evidence: On main after the first repair, `ruff check .` passes with the default rules. With the restored rules it reports 12 findings: UP042 3, S106 6, S105 2, S107 1.
Execution: One agent; one commit per cause. The freshness gate also failed on main in CI, because `types-networkx` had a newer release; it is updated in its own commit.

## Risks + recovery

The three enums are `StrEnum` now, so `str()` of a member returns its value. No code formats a member into text. This merge deploys nothing. Recovery: revert the merge commit.

## ux_reference

N/A — no visual change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passes every gate, and so does the same check in a sealed copy updated to the Hard Eng release candidate.
E2E: N/A — no user journey changes.
Real service: N/A — no changed code calls an outside service.
Retro: Failed check: none; the audit found the dropped rules → the rules are back (the audit list stays the prevention).

Delivery target: Merge
Delivery: Pending — PR, then merge and confirm main CI passes.
