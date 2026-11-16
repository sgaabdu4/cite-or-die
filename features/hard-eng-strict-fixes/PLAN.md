# Pass the strict Hard Eng rules, 2026-11-16

Status: Draft

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

- [ ] N/A — dependency metadata only: the freshness and vulnerability gates report nothing, and the tests still pass with the new versions.
- [ ] The corpus download follows a redirect, writes the body and fails on an error status → `tests/unit/test_download_scripts.py::test_download_follows_a_redirect_and_writes_the_body` and `tests/unit/test_download_scripts.py::test_download_fails_on_an_error_status`
- [ ] The T2-RAGBench line reader splits only on newline bytes, as `urlopen` iteration did → `tests/unit/test_download_scripts.py::test_json_lines_split_only_on_newline_bytes`
- [ ] The authorizer and the BM25 index type-check without an ignore comment → N/A — a type check: `mypy src/cite_or_die app` and `pyrefly check` report no issue.
- [ ] The provider settings file keeps mode 0o600 on every platform → `tests/unit/test_runtime_config.py::test_file_mode_is_0o600`
- [ ] Each compliance document has a reader → N/A — documentation links: the whole-project pass reports no unnamed markdown file.

## Baseline + execution

Result: Pending
Evidence: Pending
Execution: One builder in a fresh clone.

## Risks + recovery

The download scripts reach the network, so a real download is not part of the checks. Recovery: revert the commit.

## ux_reference

N/A — no visual change.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no runtime behavior changes; the existing tests exercise the code.
Retro: Pending

Delivery target: PR
Delivery: Pending — draft PR, then CI.
