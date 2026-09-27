"""Per-tenant encrypted runtime provider config.

Storage layout: ``data/tenants/{tenant_id}/provider.enc``. File mode ``0o600``.
On-disk bytes are ``<12-byte nonce> || AES-256-GCM(ciphertext+tag)`` over the
JSON-serialised :class:`ProviderConfigStored` payload.

Per-tenant encryption keys are derived from ``Settings.auth_secret`` via HKDF
(RFC 5869, https://datatracker.ietf.org/doc/html/rfc5869) with
``info=f"cod-runtime-provider:{tenant_id}"`` and a fixed-length 32-byte output.
This means cross-tenant blobs are not interchangeable, rotating
``auth_secret`` makes existing overrides unreadable until an admin deletes and
recreates them, and an attacker with the ciphertext but no ``auth_secret``
cannot recover the key — the API never returns the plaintext key after it is
written.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    EmbeddingProviderType,
    ProviderConfigInput,
    ProviderConfigStatus,
    ProviderConfigStored,
    RerankerProviderType,
)
from cite_or_die.retrieval.embeddings import default_embedding_dim
from cite_or_die.retrieval.local_models import local_model_dependency_error

_KDF_INFO_PREFIX = b"cod-runtime-provider:"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_PROVIDER_DEFAULT_MODELS = {
    "fake": "fake-local",
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-5.5",
    "openai-compatible": "model",
    "ollama": "qwen3:8b",
}


class InvalidTenantIdError(ValueError):
    """Raised when ``tenant_id`` fails the whitelist used for on-disk paths."""


class ProviderConfigUnreadableError(RuntimeError):
    pass


class ProviderConfigInvalidError(ValueError):
    pass


def _validate_tenant_id(tenant_id: str) -> None:
    if not _TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise InvalidTenantIdError("tenant_id must match ^[A-Za-z0-9_-]{1,64}$ for on-disk storage")


def _derive_key(auth_secret: str, tenant_id: str) -> bytes:
    """HKDF-SHA256(auth_secret, info='cod-runtime-provider:{tenant_id}', length=32)."""

    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_BYTES,
        salt=None,
        info=_KDF_INFO_PREFIX + tenant_id.encode("utf-8"),
    )
    return hkdf.derive(auth_secret.encode("utf-8"))


def _fingerprint(api_key: str | None) -> str | None:
    """Stable, leak-safe identifier for an API key (last 4 + sha256 prefix)."""

    if not api_key:
        return None
    digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8]
    tail = api_key[-4:] if len(api_key) >= 4 else "*" * len(api_key)
    return f"…{tail} (sha256:{digest})"


def effective_provider_config(
    config: ProviderConfigInput,
    previous: ProviderConfigStored | None,
    settings: Settings,
) -> ProviderConfigInput:
    base_url = _effective_provider_base_url(config, previous, settings)
    model = _effective_provider_model(config, previous, settings, base_url)
    return config.model_copy(update={"llm_model": model, "llm_base_url": base_url})


def provider_default_model(provider: str, base_url: str | None = None) -> str:
    if provider == "openai-compatible" and is_gemini_base_url(base_url or ""):
        return "gemini-3.5-flash"
    return _PROVIDER_DEFAULT_MODELS[provider]


def is_gemini_base_url(base_url: str) -> bool:
    return base_url.rstrip("/") == _GEMINI_OPENAI_BASE_URL


def _effective_provider_model(
    config: ProviderConfigInput,
    previous: ProviderConfigStored | None,
    settings: Settings,
    base_url: str | None,
) -> str:
    if config.llm_model:
        return config.llm_model
    if previous is None or previous.llm_provider != config.llm_provider:
        return provider_default_model(config.llm_provider, base_url)
    if config.llm_provider in {"openai-compatible", "ollama"}:
        previous_base_url = _previous_provider_base_url(previous, settings)
        if previous_base_url and (base_url or "").rstrip("/") == previous_base_url:
            return previous.llm_model
        return provider_default_model(config.llm_provider, base_url)
    return previous.llm_model


def _previous_provider_base_url(previous: ProviderConfigStored, settings: Settings) -> str | None:
    if previous.llm_provider == "openai-compatible":
        return (previous.llm_base_url or settings.openai_compatible_base_url).rstrip("/")
    if previous.llm_provider == "ollama":
        return (previous.llm_base_url or settings.ollama_base_url).rstrip("/")
    return previous.llm_base_url


def _effective_provider_base_url(
    config: ProviderConfigInput,
    previous: ProviderConfigStored | None,
    settings: Settings,
) -> str | None:
    if config.llm_provider == "openai-compatible":
        return (
            config.llm_base_url
            or (
                previous.llm_base_url
                if previous is not None and previous.llm_provider == config.llm_provider
                else None
            )
            or settings.openai_compatible_base_url
        ).rstrip("/")
    if config.llm_provider == "ollama":
        return (
            config.llm_base_url
            or (
                previous.llm_base_url
                if previous is not None and previous.llm_provider == config.llm_provider
                else None
            )
            or settings.ollama_base_url
        ).rstrip("/")
    return config.llm_base_url


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".provider.enc.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of the temp file on any failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


class RuntimeConfigStore:
    """File-backed AES-256-GCM store for per-tenant provider overrides."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: dict[str, ProviderConfigStored | None] = {}

    def _tenant_dir(self, tenant_id: str) -> Path:
        return self.settings.data_dir / "tenants" / tenant_id

    def _path(self, tenant_id: str) -> Path:
        return self._tenant_dir(tenant_id) / "provider.enc"

    def _key(self, tenant_id: str) -> bytes:
        return _derive_key(self.settings.auth_secret.get_secret_value(), tenant_id)

    def has_config(self, tenant_id: str) -> bool:
        _validate_tenant_id(tenant_id)
        return self._path(tenant_id).exists()

    def load(self, tenant_id: str) -> ProviderConfigStored | None:
        """Decrypt and return the override. ``None`` only when no config exists."""

        _validate_tenant_id(tenant_id)
        path = self._path(tenant_id)
        if tenant_id in self._cache and not path.exists():
            return None
        if not path.exists():
            self._cache[tenant_id] = None
            return None
        blob = path.read_bytes()
        if len(blob) <= _NONCE_BYTES:
            raise ProviderConfigUnreadableError("provider config is unreadable")
        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        try:
            plaintext = AESGCM(self._key(tenant_id)).decrypt(nonce, ciphertext, None)
        except InvalidTag as exc:
            raise ProviderConfigUnreadableError("provider config is unreadable") from exc
        try:
            data = json.loads(plaintext.decode("utf-8"))
            stored = ProviderConfigStored.model_validate(data)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderConfigUnreadableError("provider config is unreadable") from exc
        return stored

    def save(
        self,
        tenant_id: str,
        config: ProviderConfigInput,
        actor: str,
    ) -> tuple[ProviderConfigStatus, bool]:
        _validate_tenant_id(tenant_id)
        """Persist ``config`` for ``tenant_id``. Returns (status, requires_reindex).

        ``requires_reindex`` is True when the embedding provider or dim differs
        from the previously stored override (or, if none, from the server
        default) — existing Qdrant vectors are tied to the old model.
        """

        previous = self.load(tenant_id)
        retrieval = effective_retrieval_settings(config, previous, self.settings)
        dependency_error = local_model_dependency_error(
            retrieval.embedding_provider, retrieval.reranker_provider
        )
        if dependency_error is not None:
            raise ProviderConfigInvalidError(dependency_error)
        effective = effective_provider_config(config, previous, self.settings)
        effective_model = effective.llm_model or provider_default_model(
            effective.llm_provider, effective.llm_base_url
        )
        effective_base_url = effective.llm_base_url
        effective_key_plain = (
            config.llm_api_key.get_secret_value() if config.llm_api_key is not None else None
        )
        if (
            effective_key_plain is None
            and previous is not None
            and _can_reuse_stored_api_key(previous, effective, self.settings)
        ):
            effective_key_plain = previous.llm_api_key_plaintext

        stored = ProviderConfigStored(
            llm_provider=config.llm_provider,
            llm_model=effective_model,
            llm_base_url=effective_base_url,
            llm_api_key_plaintext=effective_key_plain,
            embedding_provider=retrieval.embedding_provider,
            embedding_dim=retrieval.embedding_dim,
            reranker_provider=retrieval.reranker_provider,
            requires_reindex=(
                (previous.requires_reindex if previous else False)
                or retrieval.embedding_provider != retrieval.baseline_embedding_provider
                or retrieval.embedding_dim != retrieval.baseline_embedding_dim
            ),
            configured_at=datetime.now(UTC),
            configured_by=actor,
        )
        self._write(tenant_id, stored)
        self._cache.pop(tenant_id, None)

        requires_reindex = stored.requires_reindex
        return self._to_status(stored, requires_reindex=requires_reindex), requires_reindex

    def clear_reindex_required(
        self, tenant_id: str, expected: ProviderConfigStored | None = None
    ) -> ProviderConfigStatus | None:
        _validate_tenant_id(tenant_id)
        stored = self.load(tenant_id)
        if stored is None:
            return None
        if expected is not None and (
            stored.embedding_provider != expected.embedding_provider
            or stored.embedding_dim != expected.embedding_dim
        ):
            return self._to_status(stored, requires_reindex=stored.requires_reindex)
        if stored.requires_reindex:
            stored = stored.model_copy(update={"requires_reindex": False})
            self._write(tenant_id, stored)
            self._cache.pop(tenant_id, None)
        return self._to_status(stored, requires_reindex=False)

    def status(self, tenant_id: str) -> ProviderConfigStatus | None:
        stored = self.load(tenant_id)
        if stored is None:
            return None
        return self._to_status(stored, requires_reindex=stored.requires_reindex)

    def delete(self, tenant_id: str) -> bool:
        _validate_tenant_id(tenant_id)
        path = self._path(tenant_id)
        existed = path.exists()
        if existed:
            try:
                path.unlink()
            except FileNotFoundError:
                existed = False
        self._cache[tenant_id] = None
        return existed

    def invalidate(self, tenant_id: str) -> None:
        self._cache.pop(tenant_id, None)

    def _write(self, tenant_id: str, stored: ProviderConfigStored) -> None:
        payload = stored.model_dump(mode="json")
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = AESGCM(self._key(tenant_id)).encrypt(nonce, plaintext, None)
        _atomic_write(self._path(tenant_id), nonce + ciphertext)

    @staticmethod
    def _to_status(stored: ProviderConfigStored, *, requires_reindex: bool) -> ProviderConfigStatus:
        return ProviderConfigStatus(
            llm_provider=stored.llm_provider,
            llm_model=stored.llm_model,
            llm_base_url=stored.llm_base_url,
            llm_api_key_fingerprint=_fingerprint(stored.llm_api_key_plaintext),
            embedding_provider=stored.embedding_provider,
            embedding_dim=stored.embedding_dim,
            reranker_provider=stored.reranker_provider,
            requires_reindex=requires_reindex,
            configured_at=stored.configured_at,
            configured_by=stored.configured_by,
        )


def _can_reuse_stored_api_key(
    previous: ProviderConfigStored,
    config: ProviderConfigInput,
    settings: Settings,
) -> bool:
    if previous.llm_api_key_plaintext is None:
        return False
    if previous.llm_provider != config.llm_provider:
        return False
    if config.llm_provider != "openai-compatible":
        return True
    previous_base_url = _previous_provider_base_url(previous, settings)
    new_base_url = (config.llm_base_url or settings.openai_compatible_base_url).rstrip("/")
    return bool(previous_base_url) and previous_base_url == new_base_url


class EffectiveRetrievalSettings(NamedTuple):
    embedding_provider: EmbeddingProviderType
    embedding_dim: int
    reranker_provider: RerankerProviderType
    baseline_embedding_provider: EmbeddingProviderType
    baseline_embedding_dim: int


def effective_retrieval_settings(
    config: ProviderConfigInput,
    previous: ProviderConfigStored | None,
    settings: Settings,
) -> EffectiveRetrievalSettings:
    baseline_embedding: EmbeddingProviderType = (
        previous.embedding_provider if previous else settings.embedding_provider
    )
    baseline_dim = previous.embedding_dim if previous else settings.embedding_dim
    effective_embedding: EmbeddingProviderType = config.embedding_provider or baseline_embedding
    effective_dim = _effective_embedding_dim(
        config=config,
        baseline_embedding=baseline_embedding,
        baseline_dim=baseline_dim,
        effective_embedding=effective_embedding,
    )
    effective_reranker: RerankerProviderType = config.reranker_provider or (
        previous.reranker_provider if previous else settings.reranker_provider
    )
    return EffectiveRetrievalSettings(
        embedding_provider=effective_embedding,
        embedding_dim=effective_dim,
        reranker_provider=effective_reranker,
        baseline_embedding_provider=baseline_embedding,
        baseline_embedding_dim=baseline_dim,
    )


def _effective_embedding_dim(
    *,
    config: ProviderConfigInput,
    baseline_embedding: str,
    baseline_dim: int,
    effective_embedding: str,
) -> int:
    if effective_embedding != "hash":
        return default_embedding_dim(effective_embedding)
    if config.embedding_dim is not None:
        return config.embedding_dim
    if config.embedding_provider is None or effective_embedding == baseline_embedding:
        return baseline_dim
    return default_embedding_dim(effective_embedding)
