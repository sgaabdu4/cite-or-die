from pathlib import Path

import pytest

from cite_or_die.core.config import Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        data_dir=tmp_path,
        auth_secret="test-secret-with-at-least-32-bytes",
        vector_backend="memory",
        embedding_provider="hash",
        llm_provider="fake",
    )
