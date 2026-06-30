---
name: cite-or-die
description: Evidence-first diligence acceleration workspace for active deal teams.
colors:
  ink: "#151719"
  muted: "#667078"
  line: "#dfe4e8"
  canvas: "#fbfaf7"
  panel: "#ffffff"
  field: "#ffffff"
  primary: "#0e614d"
  primary-strong: "#083f33"
  warning: "#a86816"
  danger: "#8f2c35"
typography:
  headline:
    fontFamily: "Georgia, Times New Roman, serif"
    fontSize: "19px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0"
  body:
    fontFamily: "Avenir Next, Gill Sans, Trebuchet MS, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0"
  label:
    fontFamily: "Avenir Next, Gill Sans, Trebuchet MS, sans-serif"
    fontSize: "11px"
    fontWeight: 750
    lineHeight: 1.2
    letterSpacing: "0"
rounded:
  control: "7px"
  panel: "11px"
spacing:
  xs: "5px"
  sm: "8px"
  md: "14px"
  lg: "16px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.panel}"
    rounded: "{rounded.control}"
    height: "42px"
  panel:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
---

# Design System: cite-or-die

Token owner: src/cite_or_die/ui/design_tokens.css
Design system: src/cite_or_die/ui/styles.css
Component owner: src/cite_or_die/ui/index.html

## Overview

**Creative North Star: "Diligence Control Room"**

The UI is a restrained product workspace for confidential evidence review. It favors stable controls, scannable panels, dense tables, explicit state, and visible citations over decorative presentation. New due-diligence surfaces should extend the current app shell and source viewer instead of creating a separate marketing surface.

Key characteristics:

- Dense but readable analyst workflows.
- One primary action vocabulary across upload, extraction, review, and reporting.
- Evidence drawer/source viewer available wherever a claim, risk, or metric is shown.
- Confidence, owner, materiality, and review status visible near AI-assisted outputs.

## Colors

The palette is a restrained light product system: near-black text, muted slate labels, white panels, subtle dividers, a deep green primary action, amber warning, and red danger.

### Primary

- **Diligence Green** (#0e614d): primary actions, selected state, and active focus treatment.
- **Deep Diligence Green** (#083f33): hover and stronger active states.

### Neutral

- **Ink** (#151719): primary text and brand mark.
- **Muted Slate** (#667078): labels, secondary metadata, and helper text.
- **Canvas** (#fbfaf7): app background.
- **Panel** (#ffffff): work surfaces, drawers, dialogs, and source panels.
- **Line** (#dfe4e8): dividers and control borders.

### State

- **Amber** (#a86816): warnings, gaps, delayed information requests, and medium-risk signals.
- **Red** (#8f2c35): high-severity findings, blocked review states, and destructive actions.

## Typography

**Display Font:** Georgia, "Times New Roman", serif
**Body Font:** "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif
**Label Font:** "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif

The type system pairs modest serif headings with a familiar sans UI stack. It should stay compact and predictable; new dashboard headings should not use hero-scale type.

### Hierarchy

- **Headline** (700, 19px, 1.1): panel titles, dialog titles, and dashboard section titles.
- **Title** (750, 14-16px): table group headings, tabs, and workstream labels.
- **Body** (400, 14px, 1.45): content, claims, explanatory text, and source snippets.
- **Label** (750, 11px, uppercase only where already used): form labels and compact metadata.

## Elevation

Depth is mostly structural: panels use borders and light shadows, while active drawers/dialogs use the stronger raised shadow. Avoid adding shadows to every repeated row or card.

### Shadow Vocabulary

- **Raised** (`0 24px 70px rgb(17 24 32 / 14%)`): dialogs, dropdowns, and source drawers.
- **Panel** (`0 10px 34px rgb(17 24 32 / 8%)`): main work surfaces.

## Components

### Buttons

- **Shape:** compact rectangle with 7px radius.
- **Primary:** deep green background, white text, 42px minimum height.
- **Hover / Focus:** darker green hover and a 3px green focus ring at low opacity.
- **Danger:** red text or border only for destructive settings actions.

### Panels

- **Shape:** 11px radius.
- **Background:** white panel on warm off-white canvas.
- **Border:** 1px line color.
- **Shadow:** panel shadow for major surfaces only.

### Inputs / Fields

- **Style:** white field, 7px radius, 1px line border.
- **Focus:** green border plus 3px low-opacity green ring.
- **Error / Disabled:** must use text plus color, never color alone.

### Tables And Registers

- Use compact rows with stable columns for source type, workstream, materiality, confidence, owner, status, and evidence.
- Keep row actions as icon or short command buttons with accessible labels.
- Preserve source evidence links near every generated claim.

### Navigation

- Use the existing top bar and workspace shell. New due-diligence views should use tabs or segmented controls inside the workspace rather than a separate landing page.

## Do's and Don'ts

### Do:

- **Do** reuse `src/cite_or_die/ui/design_tokens.css` for shared color, radius, font, and shadow values.
- **Do** keep claims, risks, insights, and report text traceable to source evidence.
- **Do** show confidence, owner, materiality, and human review status on AI-assisted outputs.
- **Do** design for keyboard access, focus visibility, and readable dense data.

### Don't:

- **Don't** imply AI output is final deal judgement or final sign-off.
- **Don't** add a marketing hero as the primary app screen.
- **Don't** use decorative cards, gradient text, glass effects, or oversized display type in the workspace.
- **Don't** hide evidence links behind hover-only interactions.
- **Don't** weaken tenant/matter walls, source scoping, auditability, PII redaction, provider controls, or citation verification.
