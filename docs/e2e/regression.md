# E2E Regression Commands

Run the smallest existing checks that could catch the issue after E2E fixes.

## Commands

- `uv run --extra dev python -m pytest tests/integration/test_diligence_ui.py tests/integration/test_diligence_api.py`
- `node --check src/cite_or_die/ui/diligence.js`

## Notes

Prefer existing project commands.
Record skipped checks with reason and residual risk.
