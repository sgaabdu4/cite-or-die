# Share the workspace UI tokens and controls

Status: Complete

## Outcome + scope

Give the browser workspace one token stylesheet and one library for native controls, and make the page pass the measured screen rules and the look review. Controls reach 44 px, the closed citation drawer leaves the tab order, and the workspace label and the second "set up" link that repeated nearby controls go. Refresh sits next to its heading, stacked cards get more space, and the empty viewer text gets readable contrast. The look review also asked for two small behavior changes, kept in scope because the usability rules are fixed for every design: Upload and Ask stay disabled until there is a file or a question and the empty chat names the next step. Layout stays the same. Also include the two baseline gate repairs needed on this branch so the full verification suite passes: excluding Hard Eng-installed skill folders from Ruff in `pyproject.toml`, and refreshing the nine outdated direct Python and Bun dependencies, plus the three Python packages released while this work ran (`transformers`, `types-networkx`, `types-reportlab`).

## Sources + coverage

Sources: N/A — the migration request, the upcoming UI single-source scanner, and the native gate reports define the scope and affected files.
Deliverables: None.

## Repository context

Owners: `src/cite_or_die/ui/` owns the workspace and its styles. `src/cite_or_die/api/app.py` assembles and serves the workspace HTML across `/` and `/static/index.html` (including normalized static aliases). `DESIGN.md` documents the tokens and links the library index. `pyproject.toml`, `uv.lock`, `scripts/record_demo/package.json`, and `scripts/record_demo/bun.lock` own lint configuration and dependency pins.
Same cause: N/A — the upcoming UI single-source check first reported the hard-coded styles and native controls across all application UI paths; the Ruff exclusion and dependency refresh repair inherited baseline gate failures as separate commits.
Single source: `src/cite_or_die/ui/tokens.css` owns each style value, mirrored exactly in `DESIGN.md` front matter. `src/cite_or_die/ui/library/` owns the native controls used by the workspace HTML and JavaScript, indexed in `UI-LIBRARY.md`.

## Decisions + authorization

Blockers: None.
Authority: "merge each task PR once its checks pass" (user, 2026-10-07); cross-project strict-rule PRs are approved (user, 2026-11-15).

## Acceptance + steps

- [x] The upcoming UI single-source check passes with zero findings using `["src/cite_or_die/ui/library/**"]`. Every CSS token matches `DESIGN.md` front matter and `UI-LIBRARY.md` lists each library export. N/A — verified by the upcoming UI single-source scanner against all files in `ui_paths`.
- [x] The workspace renders identical markup at `/`, `/static/index.html`, and normalized static aliases without in-process caching so template edits take effect immediately. `tests/integration/test_phase3_ui.py::test_phase3_ui_wires_streaming_and_pdfjs` verifies all entry points and static assets.
- [x] Every button and form control on the default page, the open citation drawer and the provider dialog fields measures at least 44 px, the closed drawer takes no focus, and the header holds at most one secondary line, at 390, 768 and 1280 px. `tests/integration/test_phase3_ui.py::test_base_controls_meet_the_44_pixel_tap_size`, `tests/integration/test_phase3_ui.py::test_closed_citation_drawer_is_hidden_by_css_not_aria_hidden`, `tests/integration/test_phase3_ui.py::test_provider_status_has_no_second_setup_link`, `tests/integration/test_phase3_ui.py::test_sources_refresh_sits_next_to_its_heading_and_the_drawer_toolbar_keeps_its_edge` and `tests/integration/test_phase3_ui.py::test_empty_viewer_text_uses_the_darker_hint_colour_for_contrast` cover the rules, and `browser capture` and `browser measure` report zero findings on the default page and the open drawer at all three widths. The two dialogs keep one old shared-edge measure finding in their header rows, which no capture shows.
- [x] Upload stays disabled until a file is chosen, Ask stays disabled until the question has text, the empty chat shows one line with the next step, and the first message removes that line. `tests/integration/test_phase3_ui.py::test_upload_and_ask_stay_disabled_until_there_is_something_to_send` and `tests/integration/test_phase3_ui.py::test_empty_transcript_names_the_next_step_and_the_first_message_removes_it` cover the markup, `tests/integration/test_phase3_ui.py::test_typing_a_follow_up_keeps_ask_disabled_while_an_answer_streams` covers the streaming case, and a real browser session showed Ask turn on and off with the question text.
- [x] The installed gate policy loads without unknown keys, and all native Hard Eng gates pass on this branch. N/A — verified by `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` and `make sbom`.

## Baseline + execution

Result: Passed
Evidence: Base `origin/main` (`e9162d0`) passed GitHub `test` CI, and clean `browser capture` baseline images were recorded at 390, 768, and 1280 px with 10, 10 and 9 findings (tap size, extra text, aria-hidden-focus). Running local `hard-eng.py check` also exposed inherited Ruff S607 and format findings on `.agents/skills/client-report/scripts/check_report.py` and nine outdated direct dependencies across Python and Bun.
Execution: Extract CSS values into `tokens.css` and `DESIGN.md`, move native controls into `src/cite_or_die/ui/library/`, assemble the workspace HTML in `src/cite_or_die/api/app.py` across `/` and `_WorkspaceStaticFiles`, repair the Ruff exclusion and dependency freshness in separate commits, fix the measured and look findings, and verify with full checks, clean captures, and independent review.

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

- Mistake-proof: Pass — Upload stays disabled until a file is chosen, and Ask stays disabled until the question has text.
- Least effort: Pass — 0 clicks added; each journey takes the same clicks.
- Observe: N/A — the screen records nothing for the person.
- Undo: N/A — no delete, cancel or reversal changes.
- No clutter: Pass — 16 kept, 2 removed (the "Workspace" label that repeated the tenant and matter fields, and the "set up" link that repeated the Provider button).
- Hierarchy: Pass — no action is filled while there is nothing to send; Upload and Ask are quiet until they have a file or a question.
- Alignment: Pass — each block keeps its left edge, and Refresh sits next to the Sources heading.
- Spacing: Pass — the spacing tokens are unchanged; stacked cards use the 16 px token, larger than the gaps inside a card.
- Design system: Pass — one new token, `--size-44`, in `tokens.css` and `DESIGN.md`; the unused 38 px and 42 px tokens go, and the empty viewer text uses the existing hint colour token.
- Messages: Pass — the status says the provider is not configured, the Provider button sits next to it, and the empty chat says to add a source first.
- States: Pass — the empty chat says "Add a source, then ask a question."; the closed citation drawer is hidden, so it takes no focus.
- Time: N/A — the screen shows no times.
- Audit: N/A — the app has no staff or admin roles.
- Accessibility: Pass — every button and form control measures 44 px at all three widths, the closed drawer no longer breaks the aria-hidden focus rule, and the empty viewer text has AA contrast.
- Widths: Pass — 390, 768 and 1280 px each show zero findings.
- Performance: Pass — no new data reads or payload; the CSS gains one token and loses two.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py browser capture` of the live app at `/` reported zero findings at 390, 768 and 1280 px after the fixes, against 10, 10 and 9 before, and `browser measure` of the open citation drawer reported zero findings at the same widths. `tests/integration/test_phase3_ui.py` passes with new tests for each fix.
E2E: Passed — clean live-server `browser capture` of `/` at 390, 768 and 1280 px shows the same layout with taller controls and no findings, and `tests/integration/test_phase3_ui.py` passes.
Real service: N/A — this change refactors static UI assembly, styles, native controls, lint config, and dependency locks without adding external service calls.
Retro: Keeping workspace index aliases inside `_WorkspaceStaticFiles.get_response` (never falling through to `super().get_response` for `index.html`) and revalidating solely via the assembled HTML `ETag` prevents raw-template leaks and stale 304 responses during saves, offloads file reads via `asyncio.to_thread`, avoids `@cache` (HE-HOT-PATH), and keeps server Python code out of `StaticFiles`. Excluding Hard Eng-installed skill folders via `[tool.ruff].extend-exclude` fixes the Ruff S607 and format findings without editing managed skill files. Hiding a closed drawer with `visibility` instead of `aria-hidden` removes its buttons from the tab order and from the measure.

Delivery target: PR
Delivery: Pending — push `fix/ui-single-source`, open the PR to `main`, and verify `python3 .hooks/hard-eng.py pr-text`.
