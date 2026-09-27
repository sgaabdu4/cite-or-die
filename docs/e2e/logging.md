# E2E Logging

Capture every available safe log stream during E2E runs.

## Browser

- Console errors: yes when driver supports it
- Network failures: yes when driver supports it

## App

- Dev server command: local `uvicorn cite_or_die.api.app:app`
- Device logs: not applicable
- Test runner logs: `docs/e2e/<RUN_ID>/logs/diligence-workflow.log`
- App audit/event logs: local SQLite audit is exercised by integration tests, not copied to E2E artifacts

## Notes

Do not expose secrets in reports.
Redact tokens, cookies, private customer data, and credentials.
