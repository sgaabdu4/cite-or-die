# Share the workspace UI tokens and controls

Status: Complete

## Outcome + scope

Give the browser workspace one token stylesheet and one library for native controls, and make the page pass the measured screen rules. Controls reach 44 px, the closed citation drawer leaves the tab order, and the workspace label that repeated the tenant and matter fields goes. Layout and flows stay the same. Also include the baseline gate repair of refreshing the nine outdated direct Python and Bun dependencies.

## Sources + coverage

Sources: N/A — the migration request, the upcoming UI single-source scanner, and the native gate reports define the scope and affected files.
Deliverables: None.

## Repository context

Owners: `src/cite_or_die/ui/` owns the workspace and its styles. `src/cite_or_die/api/app.py` assembles and serves the workspace HTML across `/` and `/static/index.html` (including normalized static aliases). `DESIGN.md` documents the tokens and links the library index. `pyproject.toml`, `uv.lock`, `scripts/record_demo/package.json`, and `scripts/record_demo/bun.lock` own lint configuration and dependency pins.
Same cause: N/A — the upcoming UI single-source check first reported the hard-coded styles and native controls across all application UI paths; the dependency refresh repairs inherited baseline gate failures as its own commit.
Single source: `src/cite_or_die/ui/tokens.css` owns each style value, mirrored exactly in `DESIGN.md` front matter. `src/cite_or_die/ui/library/` owns the native controls used by the workspace HTML and JavaScript, indexed in `UI-LIBRARY.md`.

## Decisions + authorization

Blockers: None.
Authority: "merge each task PR once its checks pass" (user, 2026-10-07); cross-project strict-rule PRs are approved (user, 2026-11-15).

## Acceptance + steps

- [x] The upcoming UI single-source check passes with zero findings using `["src/cite_or_die/ui/library/**"]`. Every CSS token matches `DESIGN.md` front matter and `UI-LIBRARY.md` lists each library export. N/A — verified by the upcoming UI single-source scanner against all files in `ui_paths`.
- [x] The workspace renders identical markup at `/`, `/static/index.html`, and normalized static aliases without in-process caching so template edits take effect immediately. `tests/integration/test_phase3_ui.py::test_phase3_ui_wires_streaming_and_pdfjs` verifies all entry points and static assets.
- [x] Every button and form control measures at least 44 px, the closed citation drawer takes no focus, and the header holds at most one secondary line, at 390, 768 and 1280 px. `tests/integration/test_phase3_ui.py::test_base_controls_meet_the_44_pixel_tap_size` and `test_closed_citation_drawer_is_hidden_by_css_not_aria_hidden` cover the rules, and `browser capture` reports zero findings at all three widths.
- [x] The installed gate policy loads without unknown keys, and all native Hard Eng gates pass on this branch. N/A — verified by `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` and `make sbom`.

## Baseline + execution

Result: Passed
Evidence: Base `origin/main` (`e9162d0`) passed GitHub `test` CI, and clean `browser capture` baseline images were recorded at 390, 768, and 1280 px with 10, 10 and 9 findings (tap size, extra text, aria-hidden-focus). Running local `hard-eng.py check` also exposed nine outdated direct dependencies across Python and Bun.
Execution: Extract CSS values into `tokens.css` and `DESIGN.md`, move native controls into `src/cite_or_die/ui/library/`, assemble the workspace HTML in `src/cite_or_die/api/app.py` across `/` and `_WorkspaceStaticFiles`, repair dependency freshness in its own commit, fix the measured findings, and verify with full checks, clean captures, and independent review.

## Risks + recovery

A missing HTML fragment or CSS token could break initial workspace rendering, larger controls could change the layout, and dependency updates could affect API or SBOM behavior. Integration tests cover both workspace entry points, `make sbom` verifies CycloneDX 9.0.0, and clean browser captures at three widths show the final layout. Revert the branch commits to recover.

## ux_reference

Result: Passed
Evidence: Rendered the real app at `/` and inspected the Before and After captures at 390, 768 and 1280 px; the measure reports zero findings after, against 10, 10 and 9 before.
Surface: Existing — /, rendered by `src/cite_or_die/ui/library/*.html` and `src/cite_or_die/ui/*.css`
Before: ![Before](.hard-eng/browser/ui-ssot-before-1280.png)
Proposed: ![After](.hard-eng/browser/ui-ssot-after-1280.png)
Controls: Button — reuses `src/cite_or_die/ui/styles.css`; Text field — reuses `src/cite_or_die/ui/styles.css`; Disclosure summary — reuses `src/cite_or_die/ui/styles.css`
Capture: `browser capture` of the running app at 390, 768 and 1280 px from a clean tree, with no documents and an unconfigured provider; each record has no finding.
Review: Inspected the header, sources pane, composer and closed drawer at the three widths; the layout is the same and the controls are taller.
Rules:

- Mistake-proof: N/A — no choice or data entry changes.
- Least effort: Pass — 0 clicks added; each journey takes the same clicks.
- Observe: N/A — the screen records nothing for the person.
- Undo: N/A — no delete, cancel or reversal changes.
- No clutter: Pass — 16 kept, 1 removed (the "Workspace" label that repeated the tenant and matter fields next to it).
- Hierarchy: Pass — Upload and Ask stay the only filled buttons in their groups.
- Alignment: Pass — each block keeps its left edge.
- Spacing: Pass — the spacing tokens are unchanged.
- Design system: Pass — one new token, `--size-44`, in `tokens.css` and `DESIGN.md`; the unused 38 px and 42 px tokens go.
- Messages: N/A — no message text changes.
- States: Pass — the closed citation drawer is hidden, so it takes no focus; the empty and unconfigured provider states look the same.
- Time: N/A — the screen shows no times.
- Audit: N/A — the app has no staff or admin roles.
- Accessibility: Pass — every button and form control measures 44 px at all three widths, and the closed drawer no longer breaks the aria-hidden focus rule.
- Widths: Pass — 390, 768 and 1280 px each show zero findings.
- Performance: Pass — no new data reads or payload; the CSS gains one token and loses two.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py browser capture` of the live app at `/` reported zero findings at 390, 768 and 1280 px after the fixes, against 10, 10 and 9 before. `tests/integration/test_phase3_ui.py` passes with two new tests for the 44 px controls and the hidden closed drawer.
E2E: Passed — clean live-server `browser capture` of `/` at 390, 768 and 1280 px shows the same layout with taller controls and no findings, and `tests/integration/test_phase3_ui.py` passes.
Real service: N/A — this change refactors static UI assembly, styles, native controls, lint config, and dependency locks without adding external service calls.
Retro: Keeping workspace index aliases inside `_WorkspaceStaticFiles.get_response` (never falling through to `super().get_response` for `index.html`) and revalidating solely via the assembled HTML `ETag` prevents raw-template leaks and stale 304 responses during saves, offloads file reads via `asyncio.to_thread`, avoids `@cache` (HE-HOT-PATH), and keeps server Python code out of `StaticFiles`. Hiding a closed drawer with `visibility` instead of `aria-hidden` removes its buttons from the tab order and from the measure.

Delivery target: PR
Delivery: Pending — push `fix/ui-single-source`, open the PR to `main`, and verify `python3 .hooks/hard-eng.py pr-text`.
