# Restore required verification

Status: Complete

## Outcome + scope

Repair the strict checks restored by the supported Hard Eng installation without removing product behavior or suppressing findings.

## Repository context

Owners: Python application, existing tests, demo recorder, native manifests and workflows.
Same cause: The retired checker installation did not enforce the current annotation, import, dependency, workflow and performance requirements. The first restored baseline exposed those failures.

## Decisions + authorization

Authority: The user authorized all vulnerability repairs, latest packages, necessary local model compatibility changes and delivery to main. The personal one-PR rule requires this repair and the dependency update in one product PR.
Blockers: None.
Handoff: Approval

## Acceptance + steps

- [x] Strict native checks pass with every prior runtime test retained. N/A — native reports prove static requirements; existing integration and adversarial tests prove behavior.
- [x] Provider calls and SQLite storage retain their behavior after removing duplicated setup, proved by `tests/integration/test_service.py::test_upload_chat_round_trip`.
- [x] Optional model guards retain their model selection, thresholds and score scale, proved by `tests/unit/test_model_guard.py::test_model_guard_preserves_models_thresholds_and_scores`.
- [x] Explicitly enabled model guards fail visibly when initialization fails, proved by `tests/unit/test_model_guard.py::test_enabled_model_guard_does_not_silently_fall_back`.
- [x] Existing load and regression budgets have representative passing evidence and deliberate failure proof. N/A — the native performance gate and separate deliberate-failure checks verify the existing numerical budgets.

## Baseline + execution

Result: Passed
Evidence: The initial restored baseline passed 106 Python tests, both recorder tests, evaluations and OSV scans, but failed static, workflow and dependency checks and lacked performance proof. The repaired full run passed 111 Python tests, both recorder tests, performance, evaluations, security, dependency and workflow checks. Its sole remaining diagnostic was the deprecated load-server lifespan annotation; focused Pyrefly passed after correction. The subsequent full native Ready gate passed every check.
Execution: Repair exact diagnostics, run focused checks, then run the full native gate. Deliver the repair and dependency updates together under the personal one-PR rule; required remote checks remain mandatory.

## Risks + recovery

Framework entrypoints are not dead code merely because a scanner cannot resolve them. Preserve real routes, model fields and callbacks. Use native framework-aware analysis with deliberate failure proof. Keep existing performance budgets and disclose model-weight or production-load proof that has not run.

## ux_reference

N/A — no intended user interface changes.

## Verification

Result: Passed
Follow-up: Required pre-push checks passed, but the optional mutation report exposed the old mutmut 2.5.1 CLI rejecting multiple function filters. The declared development dependency is now stable 3.8.0. A temporary two-function project used the actual native configuration, command and result parser; all four deliberately introduced mutants were killed. The locked environment installed successfully and the refreshed 226-package Python lock passed OSV. The advisory mutation time budget remains unchanged; final pre-push checks remain required.
Evidence: The final full native Ready gate passed after the annotation and CI check-name corrections. Strict source types, annotations, import boundaries, duplicate removal and dependency checks passed. Existing provider, storage and API behavior passed, including all 111 runtime tests and both recorder tests. Model-guard regressions failed before replacement and passed after it; tiny real Transformers pipelines matched reference scores. The full production weights were not downloaded. Framework-aware dead-code and recorder import-boundary checks passed and rejected deliberately invalid code. The performance run compared actual locked main at 44.554 ms with current code at 42.663 ms, then completed 301 chats with no failures; retrieval P95 was 0.64 ms and chat P95 was 19 ms. Separate synthetic reports proved rejection of an 11 percent regression, both P95 limits and a failed chat request without changing the real reports. Workflow and deployment static checks passed.
E2E: Passed — existing upload, chat, tenant isolation and citation tests passed. The real browser video journey passed, including playable output and server cleanup.
Delivery target: Merge
Delivery: Pending — current native checks and required pull request checks must pass before merge.
