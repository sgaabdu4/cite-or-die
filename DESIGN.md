# cite-or-die Design

## Overview

The browser workspace combines document upload, chat, and source evidence. The top bar exposes tenant, matter, authentication, and provider settings. The CLI supports the same ingest and chat flow. This inventory describes the existing interface; no visual change is proposed.

## Colors

[styles.css](src/cite_or_die/ui/styles.css) defines ink `#151719`, muted text `#667078`, borders `#dfe4e8`, paper `#fbfaf7`, white panels, green actions `#0e614d`, dark green `#083f33`, amber `#a86816`, and red `#8f2c35`.

## Typography

Body controls use Avenir Next, Gill Sans, Trebuchet MS, and sans-serif fallbacks. Headings use Georgia and Times New Roman. Primary heading size is 27px; secondary heading size is 19px.

## Layout

The shell uses a top bar and workspace with 16px outer padding and a 1380px maximum width. The minimum viewport width is 320px. Workspace controls wrap. Dialogs and source panes adapt through the existing CSS rules.

## Components

- Atoms: labelled inputs, action buttons, citation chips, status labels, and source text.
- Molecules: tenant/matter controls, provider status, upload controls, and citation references.
- Organisms: workspace setup dialog, provider settings dialog, chat panel, and source reader.
- Template and page: the single workspace in [index.html](src/cite_or_die/ui/index.html), including loading, empty, error, and evidence states.

## Do's and Don'ts

Keep source evidence tied to the active tenant and matter. Preserve visible focus states, labelled dialogs, disabled loading controls, and explicit provider privacy guidance. Provider keys must never return to the browser after storage.
