# Fix the two open dialog measure and look findings

Status: Draft

## Outcome + scope

Make the measure record of the provider dialog and the workspace dialog clean at 390, 768 and 1280 px, and give every form field an outline that meets 3 to 1 contrast. The `shared-edge` finding sat on the footer button row of both dialogs, not on the header: the buttons sat at the right edge while the hint text sat at the left. At 390 px the provider dialog also scrolled sideways, because its selects set the width of the form. The footer buttons now start at the left edge with the text, the two forms and the provider fieldsets and labels shrink to the dialog, and the two hint texts share one rule. The provider hint now holds 15 words and wraps to two lines at 390 px, so the measure's secondary text limit (20 words) holds. The re-index notice is one alert in plain text, and the line after Save says "Saved." and no longer repeats the notice. One opaque token, `field-line`, replaces the pale outline of text fields, text areas and selects, and a focused field still turns its border green. The `look` reviews of the two dialogs asked for eight more small changes on the same screens, kept in scope because the usability rules are fixed for every design: dialog fields fill their row, selects and headings use the ink colour, buttons, summaries and selects show a green focus outline in place of the browser blue, the Model hint is short enough to fit, the section titles use the heading font, the "Setup" eyebrow above "Workspace" goes because it repeats the button that opens the dialog, "Forget settings" stays off, in a quiet grey, until a provider config is stored, and the Sources resize handle takes the `field-line` colour for 3 to 1 contrast. Layout, copy meaning and the one light theme stay the same, and no dark theme is added.

## Sources + coverage

Sources: N/A — the request names the two open `shared-edge` and `look` items left by the earlier UI single-source PR.
Deliverables: None.

## Repository context

Owners: `src/cite_or_die/ui/tokens.css` owns each style value, mirrored in `DESIGN.md` front matter. `src/cite_or_die/ui/styles.css` and `src/cite_or_die/ui/workspace.css` own the dialog and field styles. `src/cite_or_die/ui/library/provider_dialog.html` and `src/cite_or_die/ui/library/workspace_dialog.html` own the dialog markup. `src/cite_or_die/ui/settings_panel.js` owns the provider dialog messages.
Same cause: the earlier plan `PLAN.md` (PR 34) recorded the `shared-edge` finding as old and unmeasured by capture. Measuring each dialog in an open session shows it on the footer row in both dialogs, and at 390 px the provider form is wider than its dialog. The re-index notice and the Save line show the same state in two places, and the notice box kept its text inset from the footer edge; both are fixed here. Searched `src/` for other field outlines: the global `input, textarea` rule and the provider dialog `input, select` rule were the only two, and both now use `field-line`. Searched `src/` for `prefers-color-scheme`, `color-scheme` and `data-theme`: only `color-scheme: light` in `styles.css`, so the app has one theme.
Single source: `src/cite_or_die/ui/tokens.css` owns `--color-field-line`, mirrored in `DESIGN.md`. The two copies of the dialog hint rule (`.settings-hint` and `.setup-hint`) merge into `.dialog-hint` in `styles.css`, with the size token renamed `--size-dialog-hint`. `--color-settings-field-line`, `--color-settings-hint-line` and `--color-settings-hint-surface` go, because nothing else uses them.

## Decisions + authorization

Blockers: None.
Authority: "merge each task PR once its checks pass" (user, 2026-10-07); cross-project strict-rule PRs are approved (user, 2026-11-15).

## Acceptance + steps

- [ ] The provider dialog and the workspace dialog measure with zero findings at 390, 768 and 1280 px in an open session, including the provider dialog with the re-index notice and the Save line shown. `tests/integration/test_phase3_ui.py::test_dialog_forms_shrink_to_the_dialog_and_footer_buttons_start_at_the_text_edge` and `tests/integration/test_phase3_ui.py::test_reindex_notice_is_one_alert_and_the_save_line_does_not_repeat_it` cover the markup and styles, and `browser measure` records `fu-prov-a`, `fu-prov-states` and `fu-setup-a` at the three widths show no finding.
- [ ] Every text field, text area and select outline uses `--color-field-line`, which measures at least 3 to 1 against white, paper, the composer surface and the switcher surface. `tests/integration/test_phase3_ui.py::test_field_outline_meets_three_to_one_on_every_surface_a_field_sits_on` and `tests/integration/test_phase3_ui.py::test_every_field_outline_uses_the_one_field_line_token` cover it, and `DESIGN.md` records the token and the single light theme.
- [ ] The workspace page keeps zero measure findings at the three widths. `browser capture` records `fu-before` and `fu-after` at 390, 768 and 1280 px show no finding.
- [ ] The installed gate policy loads without unknown keys and all native Hard Eng gates pass on this branch. N/A — verified by `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete`.

## Baseline + execution

Result: Passed
Evidence: Base `origin/main` (`799b19b`) passed GitHub `test` CI. In an open session, `browser measure` of the provider dialog reported `shared-edge` at 390, 768 and 1280 px, and of the workspace dialog at 1280 px (records `fu-prov-b` and `fu-setup-b`). `browser capture` of `/` reported zero findings at the three widths (`fu-before`).
Execution: Write the failing tests, change the tokens, styles, dialog markup and Save message, measure each dialog in an open session, capture After at the three widths from a clean tree, run `look` with the installed version and with Hard Eng develop, then run both check runs and the independent review.

## Risks + recovery

A narrower form could clip a long select option, and a left-aligned footer changes where the Save button sits. The select text wraps inside its field, and the measure shows no clipped control at the three widths. Revert the branch commits to recover.

## ux_reference

Result: Passed
Evidence: Rendered the real app at `/` and opened each dialog in a real browser session. Inspected the After captures of the page, the provider dialog and the workspace dialog at 390, 768 and 1280 px. `browser measure` of each dialog, also with the re-index notice and the Save line shown, reports zero findings, against `shared-edge` in the provider dialog at all three widths and in the workspace dialog at 1280 px before.
Surface: Existing — /, rendered by `src/cite_or_die/ui/library/*.html` and `src/cite_or_die/ui/*.css`
Before: ![Before](.hard-eng/browser/fu-prov-b-390.png)
Proposed: ![After](.hard-eng/browser/fu-prov-a-390.png)
Controls: Button — reuses `src/cite_or_die/ui/styles.css`; Text field — reuses `src/cite_or_die/ui/styles.css`; Select — reuses `src/cite_or_die/ui/styles.css`
Capture: `browser capture` of `/` and `browser measure` of the open provider dialog and workspace dialog on the running app at 390, 768 and 1280 px, from a clean tree. Each record has no finding.
Review: Inspected the page, both dialogs, the footer rows, the field outlines and the focus outline at the three widths. The layout is the same; the footers start at the left edge, the provider form fits a phone, and the field outlines are darker.
Rules:

- Mistake-proof: Pass — Ask stays disabled until there is a question, and Forget settings stays off, in grey, until a provider config is stored. `tests/integration/test_phase3_ui.py::test_forget_settings_is_off_until_a_provider_config_is_stored` covers it.
- Least effort: Pass — 2 clicks; Setup then Use workspace, and Provider settings then Save, each take 2 clicks with the prefilled values, the same as before.
- Observe: Pass — the page shows the provider status and the scope without asking a person to confirm either.
- Undo: N/A — the captures show no completed change; Forget settings asks first with a confirm box.
- No clutter: Pass — 46 kept, 1 removed (the "Setup" eyebrow above "Workspace", which repeated the button that opens the dialog); the provider hint went from 38 to 15 words.
- Hierarchy: Pass — Save and Use workspace are the one filled button in each dialog, and Forget settings, Close and the two card buttons are outlined.
- Alignment: Pass — both dialog footers start at the left edge of the hint text, and each label shares an edge with its field.
- Spacing: Pass — the spacing tokens are unchanged; groups keep a larger gap than the gaps inside a group.
- Design system: Pass — one new colour token, `field-line`, in `tokens.css` and `DESIGN.md`; four tokens go (`settings-field-line`, `settings-hint-line`, `settings-hint-surface`, `resizer`), and the hint size token is renamed `dialog-hint`.
- Messages: Pass — the provider hint says keys are stored encrypted and never shown again, and the line after Save says "Saved.".
- States: Pass — the notice shows as one alert after a save that needs a re-index, the Save line is a live region, and Forget settings is off with no stored config.
- Time: N/A — the screens show no times.
- Audit: N/A — the app has no staff or admin roles.
- Accessibility: Pass — field outlines measure 3.58 to 3.77 to 1 on every surface a field sits on, the resize handle uses the same colour, buttons, summaries and selects show a green focus outline, and every control measures 44 px at the three widths.
- Widths: Pass — 390, 768 and 1280 px each show zero findings, and the provider form no longer scrolls sideways at 390 px.
- Performance: Pass — no new data reads or payload; the CSS gains one token and loses four. `tests/integration/test_phase3_ui.py` covers the styles.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — journey: open the provider dialog and the workspace dialog in a real browser at 390, 768 and 1280 px; proof: `browser measure` records with zero findings; Complete needs Passed evidence.
Real service: N/A — this change edits styles, markup and one UI message without adding external service calls.
Retro: Required on Complete plans; write it at task end.

Delivery target: PR
Delivery: Pending — required remote proof.
