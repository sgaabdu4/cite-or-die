# Fix the two open dialog measure and look findings

Status: Draft

## Outcome + scope

Make the measure record of the provider dialog and the workspace dialog clean at 390, 768 and 1280 px, and give every form field an outline that meets 3 to 1 contrast. The `shared-edge` finding sat on the footer button row of both dialogs, not on the header: the buttons sat at the right edge while the hint text sat at the left. At 390 px the provider dialog also scrolled sideways, because its selects set the width of the form. The footer buttons now start at the left edge with the text, the two forms and the provider fieldsets and labels shrink to the dialog, and the two hint texts share one rule. The provider hint now holds 19 words, so the measure's secondary text limit (20 words) holds. The re-index notice is one alert in plain text, and the line after Save says "Saved." and no longer repeats the notice. One opaque token, `field-line`, replaces the pale outline of text fields, text areas and selects. Layout, copy meaning and the one light theme stay the same, and no dark theme is added.

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

Result: Pending
Evidence: Pending
Surface: Existing — /, rendered by `src/cite_or_die/ui/library/*.html` and `src/cite_or_die/ui/*.css`
Before: ![Before](.hard-eng/browser/fu-before-1280.png)
Proposed: ![After](.hard-eng/browser/fu-after-1280.png)
Controls: Button — reuses `src/cite_or_die/ui/styles.css`; Text field — reuses `src/cite_or_die/ui/styles.css`
Capture: Pending
Review: Pending
Rules:

- Pending: Pending

## Verification

Result: Pending
Evidence: Pending
E2E: Required — journey: open the provider dialog and the workspace dialog in a real browser at 390, 768 and 1280 px; proof: `browser measure` records with zero findings; Complete needs Passed evidence.
Real service: N/A — this change edits styles, markup and one UI message without adding external service calls.
Retro: Required on Complete plans; write it at task end.

Delivery target: PR
Delivery: Pending — required remote proof.
