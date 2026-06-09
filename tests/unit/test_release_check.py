import pytest

from scripts import release_check


def test_release_check_rejects_tracked_node_modules(monkeypatch) -> None:
    monkeypatch.setattr(
        release_check,
        "_tracked_node_modules",
        lambda: ["scripts/record_demo/node_modules/playwright/index.js"],
    )

    with pytest.raises(SystemExit, match="tracked node_modules entries are not allowed"):
        release_check.main()
