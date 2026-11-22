# Share the workspace UI tokens and controls

Status: Draft

## Outcome + scope

Give the browser workspace one token stylesheet and one library for native controls. Keep the rendered layout and existing flows.

## Sources + coverage

Sources: N/A — the migration request sets the scope and its scanner report names the affected files.
Deliverables: None.

## Repository context

Owners: `src/cite_or_die/ui/` owns the workspace and its styles. `src/cite_or_die/api/app.py` serves the workspace. `DESIGN.md` documents the tokens and links the library index.
Same cause: N/A — the new UI check first reported the hard-coded styles and native controls. The scan covered all application UI paths.
Single source: `tokens.css` owns each style value, with an exact mirror in the design front matter. `ui/library/` owns the native controls used by the workspace HTML and JavaScript.

## Decisions + authorization

Blockers: The verified Hard Eng update and separate dependency repair must land on main before final verification.
Handoff: Clarification
Authority: The maintainer authorized implementation and opening a PR to `main` on 2026-11-22.

## Acceptance + steps

- [x] The UI source check passes with the shared library path. Every CSS token matches the design front matter. The generated index lists each export. N/A — verified by the UI source check and exact token and index comparisons.
- [x] The workspace renders the same markup at both existing entry points. `tests/integration/test_phase3_ui.py::test_phase3_ui_wires_streaming_and_pdfjs` verifies the page and assets.
- [x] The workspace, dialogs, upload, source selection, chat and citation viewer still work. Hard Eng captures show the same workspace. N/A — verified through the Playwright journey and browser captures at three widths.
- [x] The installed gate policy loads with the existing configuration. Its UI path includes the token stylesheet and every library file. N/A — verified with the installed policy loader and the UI source check.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Draft` passed the applicable secret checks. GitHub's `test` check passed on the same base. The workspace flows ran locally at 390, 768 and 1280 pixels.
Execution: Extract the style values, then move the native controls and compare the assembled workspace with the base.

## Risks + recovery

A missing fragment or token could break initial rendering. The workspace test loads both entry points, and browser captures check the result. Revert the workspace refactor commit to recover.

## ux_reference

N/A — unchanged: ![Before](.hard-eng/browser/ui-ssot-before-1280.png) ![After](.hard-eng/browser/ui-ssot-after-1280.png) — workspace at `/` with no documents, an unconfigured provider, and the same pane width.

## Verification

Result: Pending
Evidence: The upcoming UI source check reported zero findings. All 177 tokens matched their exact YAML values. The rendered HTML and resolved style rules matched the base after asset link changes. The release build and 135 project tests passed. Finish the full gate and repeat the captures on the repaired base.
E2E: Passed — Playwright exercised workspace setup, provider settings, upload, source selection, streaming chat, and text citations at 390, 768 and 1280 pixels. The desktop check also covered keyboard resize persistence and rendering an uploaded PDF.
Real service: N/A — this changes page assembly, styles, and native controls. It adds no outside service call.
Retro: Resolved-value comparisons caught incorrect token references. Matching pane widths made the workspace captures reproducible. The API module owns page assembly so its implementation stays outside the public static directory. The inherited lint finding goes through the upstream Hard Eng update.

Delivery target: PR
Delivery: Pending — open the PR to `main` and verify its text check.
