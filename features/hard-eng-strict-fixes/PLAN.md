# Pass the strict Hard Eng rules, 2026-11-16

Status: Complete

## Outcome + scope

Make the repository pass the strict Hard Eng rules with no regression: current packages, no known advisory in the lock file, no ignore comment that has a clean fix, and every markdown file named by a reader. Non-goals: new features and any change of what the code does.

## Repository context

Owners: `pyproject.toml` and `uv.lock` for the Python packages, `scripts/record_demo/package.json` and `bun.lock` for Playwright, `scripts/download_*.py` for the downloads, `src/cite_or_die/auth/authorizer.py` and `src/cite_or_die/retrieval/bm25.py` with the new `stubs/` folder for types, `tests/unit/test_runtime_config.py` for the file mode test, and `goal.md` for the naming of the compliance documents.
Same cause: N/A — a sealed scan found these faults for the first time; no earlier fix of them. Other places searched: `git grep "noqa\|type: ignore\|skipif"` over the source, scripts and tests found the sites listed in the PR.
Single source: The Python package bounds live in `pyproject.toml` only; the pins (`pypdf`, `sentence-transformers`, `transformers`) and upper bounds keep their old style. The HTTP download code lives in the two scripts; the three `urlopen` calls became `httpx`, which the project already depends on.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The coordinator asked for this fix wave. Nothing is merged here.

## Acceptance + steps

- [x] N/A — dependency metadata only: the freshness and vulnerability gates report nothing, and the tests still pass with the new versions.
- [x] The corpus download follows a redirect, writes the body and fails on an error status → `tests/unit/test_download_scripts.py::test_download_follows_a_redirect_and_writes_the_body` and `tests/unit/test_download_scripts.py::test_download_fails_on_an_error_status`
- [x] The T2-RAGBench line reader splits only on newline bytes, as `urlopen` iteration did → `tests/unit/test_download_scripts.py::test_json_lines_split_only_on_newline_bytes`
- [x] The authorizer and the BM25 index type-check without an ignore comment → N/A — a type check: `mypy src/cite_or_die app` and `pyrefly check` report no issue.
- [x] The provider settings file keeps mode 0o600 on every platform → `tests/unit/test_runtime_config.py::test_file_mode_is_0o600`
- [x] Each compliance document has a reader → N/A — documentation links: the whole-project pass reports no unnamed markdown file.

## Baseline + execution

Result: Passed
Evidence: On origin/main the sealed scan failed five gates: freshness (eight Python packages and Playwright), the dnspython advisory in the vulnerability and legacy security gates, and the secret history gate. The secret history result is an effect of the scan copy: a real run scans only the commits since the base commit that passed CI, and it passes. The scan also listed 11 ignore comments, one skip marker and 3 unnamed markdown files.
Execution: One builder in a fresh clone.

## Risks + recovery

The `health` edit for the demo recorder Fallow gate is held until the hooks update, for the reason in Verification. Four ignore comments stay and are held for the coordinator: three S603 subprocess calls with fixed arguments (`scripts/mutation_gate.py`, `scripts/release_check.py`, `src/cite_or_die/storage/audit.py`) and one S311 seeded sampler (`scripts/download_t2ragbench_subset.py`). Ruff offers no clean form for them: a variable command always trips S603, and the seeded sampler must keep its output. The download scripts reach the network, so a real download is not part of the checks. Recovery: revert the commit.

## ux_reference

N/A — no visual change.

## Verification

Result: Passed
Evidence: Run 1, the branch with its own `.hooks`: `python3 .hooks/hard-eng.py check --base origin/main` exit 0, 40 gates passed. Two earlier runs failed only the performance gate, which compares two benchmark means and was noisy on a loaded Mac; the gate passed alone and passed in CI. Run 2, a scratch copy with Hard Eng develop `.hooks` and `.agents`: refused for the four held ignore comments and for the demo recorder Fallow gate, which needs `health` in `--only`. With that edit applied the installed hooks fail on a Fallow note about too little git history in `scripts/record_demo`, so the edit waits for the hooks update. Run 3 is for Dart repositories and does not apply. Without `--base`, the secret history gate also scans three old test placeholder keys in main history, which CI does not scan.
E2E: N/A — no runtime behavior changes; the existing tests exercise the code.
Retro: None — no failed check beyond the findings fixed above

Delivery target: PR
Delivery: Pending — draft PR, then CI.
