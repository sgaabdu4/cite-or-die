"""Per-tenant encrypted runtime provider config.

Storage layout: ``data/tenants/{tenant_id}/provider.enc``. File mode ``0o600``.
On-disk bytes are ``<12-byte nonce> || AES-256-GCM(ciphertext+tag)`` over the
JSON-serialised :class:`ProviderConfigStored` payload.

Per-tenant encryption keys are derived from ``Settings.auth_secret`` via HKDF
(RFC 5869, https://datatracker.ietf.org/doc/html/rfc5869) with
``info=f"cod-runtime-provider:{tenant_id}"`` and a fixed-length 32-byte output.
This means cross-tenant blobs are not interchangeable, rotating
``auth_secret`` invalidates every stored override (silent fallback to defaults),
and an attacker with the ciphertext but no ``auth_secret`` cannot recover the
key — the API never returns the plaintext key after it is written.
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

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cite_or_die.core.config import Settings
from cite_or_die.core.models import (
    ProviderConfigInput,
    ProviderConfigStatus,
    ProviderConfigStored,
)

_KDF_INFO_PREFIX = b"cod-runtime-provider:"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_TENANT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InvalidTenantIdError(ValueError):
    """Raised when ``tenant_id`` fails the whitelist used for on-disk paths."""


def _validate_tenant_id(tenant_id: str) -> None:
    if not _TENANT_ID_PATTERN.fullmatch(tenant_id):
        raise InvalidTenantIdError(
            "tenant_id must match ^[A-Za-z0-9_-]{1,64}$ for on-disk storage"
        )


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
        """Decrypt and return the override. ``None`` on absence or tamper."""

        _validate_tenant_id(tenant_id)
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        path = self._path(tenant_id)
        if not path.exists():
            self._cache[tenant_id] = None
            return None
        blob = path.read_bytes()
        if len(blob) <= _NONCE_BYTES:
            self._cache[tenant_id] = None
            return None
        nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        try:
            plaintext = AESGCM(self._key(tenant_id)).decrypt(nonce, ciphertext, None)
        except InvalidTag:
            self._cache[tenant_id] = None
            return None
        try:
            data = json.loads(plaintext.decode("utf-8"))
            stored = ProviderConfigStored.model_validate(data)
        except (ValueError, UnicodeDecodeError):
            self._cache[tenant_id] = None
            return None
        self._cache[tenant_id] = stored
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
        baseline_embedding = (
            previous.embedding_provider if previous else self.settings.embedding_provider
        )
        baseline_dim = previous.embedding_dim if previous else self.settings.embedding_dim
        effective_embedding = config.embedding_provider or baseline_embedding
        effective_dim = config.embedding_dim or baseline_dim
        effective_reranker = config.reranker_provider or (
            previous.reranker_provider if previous else self.settings.reranker_provider
        )
        effective_model = config.llm_model or (
            previous.llm_model if previous else self.settings.llm_model
        )
        effective_base_url = config.llm_base_url
        if effective_base_url is None and previous is not None:
            effective_base_url = previous.llm_base_url
        effective_key_plain = (
            config.llm_api_key.get_secret_value() if config.llm_api_key is not None else None
        )
        if effective_key_plain is None and previous is not None:
            effective_key_plain = previous.llm_api_key_plaintext

        stored = ProviderConfigStored(
            llm_provider=config.llm_provider,
            llm_model=effective_model,
            llm_base_url=effective_base_url,
            llm_api_key_plaintext=effective_key_plain,
            embedding_provider=effective_embedding,
            embedding_dim=effective_dim,
            reranker_provider=effective_reranker,
            configured_at=datetime.now(UTC),
            configured_by=actor,
        )
        payload = stored.model_dump(mode="json")
        plaintext = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        nonce = secrets.token_bytes(_NONCE_BYTES)
        ciphertext = AESGCM(self._key(tenant_id)).encrypt(nonce, plaintext, None)
        _atomic_write(self._path(tenant_id), nonce + ciphertext)
        self._cache[tenant_id] = stored

        requires_reindex = (
            effective_embedding != baseline_embedding or effective_dim != baseline_dim
        )
        return self._to_status(stored, requires_reindex=requires_reindex), requires_reindex

    def status(self, tenant_id: str) -> ProviderConfigStatus | None:
        stored = self.load(tenant_id)
        if stored is None:
            return None
        return self._to_status(stored, requires_reindex=False)

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

    @staticmethod
    def _to_status(
        stored: ProviderConfigStored, *, requires_reindex: bool
    ) -> ProviderConfigStatus:
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
