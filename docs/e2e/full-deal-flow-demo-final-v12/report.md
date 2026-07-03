# E2E Report

Run: full-deal-flow-demo-final-v12
Target: http://127.0.0.1:8774
Driver: standalone Playwright after in-app browser capability check
Data mode: uploaded-fixture-files
Flow: diligence-workflow
Profiles: desktop, mobile
Capture: stable viewport, visible cursor, click bloom, and page scrolls instead of viewport changes
Actions: provider setup and save, upload, selection, cited question, review creation, accelerator run, all output tabs, evidence drawer, AI-assisted review, reruns
1x MP4 video paths:
- docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_desktop.mp4
- docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_mobile.mp4
Raw WebM paths:
- docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_desktop.webm
- docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_mobile.webm
2x cursor recap paths:
- docs/e2e/full-deal-flow-demo-final-v12/recaps/diligence-workflow_desktop_2x_cursor.mp4
- docs/e2e/full-deal-flow-demo-final-v12/recaps/diligence-workflow_mobile_2x_cursor.mp4

## Results

- desktop: passed; 1x video docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_desktop.mp4; raw docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_desktop.webm; 2x recap docs/e2e/full-deal-flow-demo-final-v12/recaps/diligence-workflow_desktop_2x_cursor.mp4
- mobile: passed; 1x video docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_mobile.mp4; raw docs/e2e/full-deal-flow-demo-final-v12/videos/diligence-workflow_mobile.webm; 2x recap docs/e2e/full-deal-flow-demo-final-v12/recaps/diligence-workflow_mobile_2x_cursor.mp4

## Regression

- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`
- `node --check src/cite_or_die/ui/app.js src/cite_or_die/ui/diligence.js src/cite_or_die/ui/setup_progress.js`

## Unresolved

None.
