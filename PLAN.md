# Share the workspace UI tokens and controls

Status: Complete

## Outcome + scope

Give the browser workspace one token stylesheet and one library for native controls, keeping the rendered layout and existing flows unchanged. Also include the two baseline gate repairs needed on this branch so the full verification suite passes: excluding Hard Eng-installed skill folders from Ruff in `pyproject.toml`, and refreshing the nine outdated direct Python and Bun dependencies.

## Sources + coverage

Sources: N/A — the migration request, the upcoming UI single-source scanner, and the native gate reports define the scope and affected files.
Deliverables: None.

## Repository context

Owners: `src/cite_or_die/ui/` owns the workspace and its styles. `src/cite_or_die/api/app.py` assembles and serves the workspace HTML across `/` and `/static/index.html` (including normalized static aliases). `DESIGN.md` documents the tokens and links the library index. `pyproject.toml`, `uv.lock`, `scripts/record_demo/package.json`, and `scripts/record_demo/bun.lock` own lint configuration and dependency pins.
Same cause: N/A — the upcoming UI single-source check first reported the hard-coded styles and native controls across all application UI paths; the Ruff exclusion and dependency refresh repair inherited baseline gate failures as separate commits.
Single source: `src/cite_or_die/ui/tokens.css` owns each style value, mirrored exactly in `DESIGN.md` front matter. `src/cite_or_die/ui/library/` owns the native controls used by the workspace HTML and JavaScript, indexed in `UI-LIBRARY.md`.

## Decisions + authorization

Blockers: None.
Authority: The maintainer authorized implementation and opening a PR to `main` on 2026-11-22.

## Acceptance + steps

- [x] The upcoming UI single-source check passes with zero findings using `["src/cite_or_die/ui/library/**"]`. Every CSS token matches `DESIGN.md` front matter and `UI-LIBRARY.md` lists each library export. N/A — verified by the upcoming UI single-source scanner against all files in `ui_paths`.
- [x] The workspace renders identical markup at `/`, `/static/index.html`, and normalized static aliases without in-process caching so template edits take effect immediately. `tests/integration/test_phase3_ui.py::test_phase3_ui_wires_streaming_and_pdfjs` verifies all entry points and static assets.
- [x] The workspace preserves identical visual appearance across 390, 768, and 1280 px while keeping existing flows working. N/A — verified by clean `origin/main` and `HEAD` `browser capture` SHA-256 parity at all three widths and `tests/integration/test_phase3_ui.py::test_phase3_ui_modules_wire_streaming_pdfjs_and_workspace_controls`.
- [x] The installed gate policy loads without unknown keys, and all native Hard Eng gates pass on this branch. N/A — verified by `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` and `make sbom`.

## Baseline + execution

Result: Passed
Evidence: Base `origin/main` (`e9162d0`) passed GitHub `test` CI, and clean `browser capture` baseline images were recorded at 390, 768, and 1280 px. Running local `hard-eng.py check` exposed inherited Ruff S607 on `.agents/skills/client-report/scripts/check_report.py` and nine outdated direct dependencies across Python and Bun.
Execution: Extract CSS values into `tokens.css` and `DESIGN.md`, move native controls into `src/cite_or_die/ui/library/`, assemble the workspace HTML in `src/cite_or_die/api/app.py` across `/` and `_WorkspaceStaticFiles`, repair the Ruff exclusion and dependency freshness in separate commits, and verify with full checks, clean captures, and independent review.

## Risks + recovery

A missing HTML fragment or CSS token could break initial workspace rendering, and dependency updates could affect API or SBOM behavior. Integration tests cover both workspace entry points, `make sbom` verifies CycloneDX 9.0.0, and clean browser captures verify pixel parity with `origin/main`. Revert the branch commits to recover.

## ux_reference

N/A — unchanged: ![Before](.hard-eng/browser/ui-ssot-before-1280.png) ![After](.hard-eng/browser/ui-ssot-after-1280.png) — workspace at `/` with no documents, an unconfigured provider, and the same pane width.

## Verification

Result: Passed
Evidence: Upcoming UI single-source scanner reported `B5_UI_HITS: 0` with `TARGET_UI_LIBRARY: ["src/cite_or_die/ui/library/**"]`. Clean measured captures at `origin/main` and `HEAD` matched byte-for-byte (`sha256` identical, `dirty: false`) at 390, 768, and 1280 px (`ui_proof.unchanged_problem is None`); pre-existing `origin/main` browser measure findings (9 at 1280 px, 10 at 390/768 px) are unchanged. Full `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all gates.
E2E: Passed — clean live-server `browser capture` verified `/` rendering at 390, 768, and 1280 px with identical SHA-256 digests against `origin/main`, and Playwright integration/recording tests plus `tests/integration/test_phase3_ui.py` passed.
Real service: N/A — this change refactors static UI assembly, styles, native controls, lint config, and dependency locks without adding external service calls.
Retro: Intercepting `_UI_INDEX_PATH` inside `_WorkspaceStaticFiles.file_response` and assembling HTML on demand removes `@cache` (HE-HOT-PATH), handles normalized static aliases (`/static/index.html/`, `/static//index.html`), and preserves live template edits during `serve --reload` while keeping server Python code out of `StaticFiles`. Excluding Hard Eng-installed skill folders via `[tool.ruff].extend-exclude` fixes Ruff S607 cleanly without editing managed skill files.

Delivery target: PR
Delivery: Pending — push `fix/ui-single-source`, open the PR to `main`, and verify `python3 .hooks/hard-eng.py pr-text`.
