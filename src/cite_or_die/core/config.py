from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Production secrets should come from Docker secrets or SOPS."""

    model_config = SettingsConfigDict(
        env_prefix="CITE_OR_DIE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["dev", "test", "prod"] = "dev"
    data_dir: Path = Path("data")
    public_base_url: str = "https://cite-or-die.localhost"

    auth_secret: SecretStr = Field(default=SecretStr("dev-only-change-me-32-bytes-minimum"))
    auth_secret_file: Path | None = None
    auth_issuer: str = "cite-or-die"
    auth_audience: str = "cite-or-die-api"
    access_token_minutes: int = 60

    vector_backend: Literal["memory", "qdrant"] = "memory"
    qdrant_url: str = "http://localhost:6333"
    embedding_provider: Literal["hash", "bge-m3"] = "hash"
    embedding_dim: int = 384

    llm_provider: Literal["fake", "anthropic", "openai", "ollama"] = "fake"
    llm_model: str = "fake-deterministic-v1"
    anthropic_api_key: SecretStr | None = None
    anthropic_api_key_file: Path | None = None
    openai_api_key: SecretStr | None = None
    openai_api_key_file: Path | None = None
    ollama_base_url: str = "http://localhost:11434"

    retrieval_top_k: int = 8
    retrieval_candidate_k: int = 50
    # Source: https://arxiv.org/pdf/2605.12028 recommends hybrid retrieval plus reranking.
    reranker_provider: Literal["lexical", "bge-reranker-v2-m3", "none"] = "lexical"
    rerank_input_k: int = 30
    chunk_size: int = 900
    chunk_overlap: int = 160
    max_upload_mb: int = 25

    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "cite_or_die.sqlite3"

    @property
    def uploads_path(self) -> Path:
        return self.data_dir / "uploads"

    @model_validator(mode="after")
    def load_secret_files(self) -> "Settings":
        if self.auth_secret_file and self.auth_secret_file.exists():
            self.auth_secret = SecretStr(self.auth_secret_file.read_text().strip())
        if self.anthropic_api_key_file and self.anthropic_api_key_file.exists():
            self.anthropic_api_key = SecretStr(self.anthropic_api_key_file.read_text().strip())
        if self.openai_api_key_file and self.openai_api_key_file.exists():
            self.openai_api_key = SecretStr(self.openai_api_key_file.read_text().strip())
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
