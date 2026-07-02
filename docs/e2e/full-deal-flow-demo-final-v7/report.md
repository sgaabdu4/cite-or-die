# E2E Report

Run: full-deal-flow-demo-final-v7
Target: http://127.0.0.1:8770
Driver: standalone Playwright after in-app browser capability check
Data mode: uploaded-fixture-files
Flow: diligence-workflow
Profiles: desktop
Actions: provider setup and save, upload, selection, cited question, review creation, accelerator run, all output tabs, evidence drawer, AI-assisted review, reruns
Video paths:
- docs/e2e/full-deal-flow-demo-final-v7/videos/diligence-workflow_desktop.webm
- docs/e2e/full-deal-flow-demo-final-v7/videos/diligence-workflow_desktop.mp4

## Results

- desktop: passed; video docs/e2e/full-deal-flow-demo-final-v7/videos/diligence-workflow_desktop.mp4

## Regression

- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`
- `node --check src/cite_or_die/ui/app.js src/cite_or_die/ui/diligence.js src/cite_or_die/ui/setup_progress.js`

## Unresolved

None.
