# E2E Demo Video Report

Run: diligence-full-demo-20260703T071406Z
Target: http://127.0.0.1:59028
Demo data directory: /tmp/diligence-full-demo-20260703T071406Z
Deal pack: /Users/abid/Downloads/cite-or-die-public-deal-pack/production-demo-upload-ready
Driver: standalone Playwright with visible cursor overlay and click bloom
Data mode: fresh local demo data only
Profiles: desktop, mobile
Layout behavior: fixed viewport with real page scrolling

## Files Uploaded

- 00-management-presentation-public-context.txt
- 01-financial-pack-fy24.txt
- 02-customer-data-export.txt
- 03-customer-contract-master-services-agreement.txt
- 04-operations-report.txt
- 05-hr-records-and-org-chart.txt
- 06-qa-log-and-information-request-list.txt
- 07-vendor-response-financial-normalisation.txt
- 08-prior-deal-precedent-and-comparable-transactions.txt
- 09-sector-benchmark-public-market-information.txt

## Covered Flow

- Provider setup
- 10-file upload
- Select all files
- Cited question over selected sources
- Source evidence drawer
- Create review from selected files
- Run accelerator
- Classified files
- Extracted facts
- Risk register
- Cross-workstream insights
- Open requests
- Report drafts
- Report citation evidence drawer
- Provider-assisted review
- Provider-assisted rerun
- Accelerator rerun
- Provider-assisted review after rerun

## Outputs Verified

- 10 sources
- 36 extracted facts
- 7 risks
- Executive, commercial, operational, and financial draft outputs
- Customer concentration and earnings quality cross-workstream insight
- Contract consent and open request cross-workstream insight

## Artifacts

- desktop 1x MP4: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/videos/diligence-full-demo_desktop.mp4
- desktop raw WebM: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/videos/diligence-full-demo_desktop.webm
- desktop 2x recap: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/recaps/diligence-full-demo_desktop_2x_cursor.mp4
- mobile 1x MP4: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/videos/diligence-full-demo_mobile.mp4
- mobile raw WebM: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/videos/diligence-full-demo_mobile.webm
- mobile 2x recap: /Users/abid/.treehouse/cite-or-die-848ca3/1/cite-or-die/docs/e2e/diligence-full-demo-20260703T071406Z/recaps/diligence-full-demo_mobile_2x_cursor.mp4
- Events: `events.jsonl`
- Screenshots: `screenshots/diligence-full-demo/`
- Sampled frames: `frames/`
- Server log: `logs/server.log`

## Regression

- `node --check src/cite_or_die/ui/app.js scripts/record_demo/diligence_full_demo.mjs` - pass
- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py` - pass
- `npm run demo:diligence-video` - pass

## Unresolved

None.
