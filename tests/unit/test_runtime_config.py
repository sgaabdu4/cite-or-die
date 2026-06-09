"""Per-tenant encrypted provider config — unit tests."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from pydantic import SecretStr

from cite_or_die.core.config import Settings
from cite_or_die.core.models import ProviderConfigInput
from cite_or_die.security.runtime_config import (
    InvalidTenantIdError,
    RuntimeConfigStore,
    _derive_key,
    _fingerprint,
)


def _settings(data_dir: Path, secret: str = "unit-test-secret-32-bytes-of-noise!!") -> Settings:
    return Settings(
        app_env="test",
        data_dir=data_dir,
        auth_secret=SecretStr(secret),
        llm_provider="fake",
        llm_model="fake-deterministic-v1",
        allow_hosted_llm=False,
    )


def test_kdf_is_deterministic_per_tenant() -> None:
    k1 = _derive_key("secret-A", "tenant-1")
    k2 = _derive_key("secret-A", "tenant-1")
    assert k1 == k2
    assert len(k1) == 32


def test_kdf_differs_between_tenants() -> None:
    k_a = _derive_key("secret-A", "tenant-1")
    k_b = _derive_key("secret-A", "tenant-2")
    assert k_a != k_b


def test_kdf_differs_between_secrets() -> None:
    k_a = _derive_key("secret-A", "tenant-1")
    k_b = _derive_key("secret-B", "tenant-1")
    assert k_a != k_b


def test_fingerprint_redacts_key_value() -> None:
    fp = _fingerprint("sk-test-1234567890abcdefXYZ4")
    assert fp is not None
    assert "sk-test-1234567890abcdef" not in fp
    assert "XYZ4" in fp
    assert "sha256:" in fp
    assert _fingerprint(None) is None
    assert _fingerprint("") is None


def test_round_trip_save_then_load(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    cfg = ProviderConfigInput(
        llm_provider="openai",
        llm_model="gpt-test-1",
        llm_api_key=SecretStr("sk-test-1234567890abcdef"),
    )
    status, requires_reindex = store.save("tenant-1", cfg, actor="setup-user")
    assert status.llm_provider == "openai"
    assert status.llm_model == "gpt-test-1"
    assert status.llm_api_key_fingerprint and "cdef" in status.llm_api_key_fingerprint
    assert requires_reindex is False

    store2 = RuntimeConfigStore(_settings(tmp_path))
    loaded = store2.load("tenant-1")
    assert loaded is not None
    assert loaded.llm_provider == "openai"
    assert loaded.llm_api_key_plaintext == "sk-test-1234567890abcdef"


def test_load_returns_none_for_missing_tenant(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    assert store.load("never-saved") is None
    assert store.status("never-saved") is None
    assert store.has_config("never-saved") is False


def test_wrong_secret_silently_fails_decrypt(tmp_path: Path) -> None:
    save_store = RuntimeConfigStore(_settings(tmp_path, secret="primary-secret-A"))
    save_store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai",
            llm_model="gpt-test-1",
            llm_api_key=SecretStr("sk-real"),
        ),
        actor="setup-user",
    )

    rotated_store = RuntimeConfigStore(_settings(tmp_path, secret="different-secret-B"))
    assert rotated_store.load("tenant-1") is None
    assert rotated_store.status("tenant-1") is None


def test_cross_tenant_decrypt_fails(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr("sk-one")
        ),
        actor="u",
    )
    # Mis-file tenant-1's ciphertext under tenant-2 and try to read it as tenant-2.
    src = tmp_path / "tenants" / "tenant-1" / "provider.enc"
    dst = tmp_path / "tenants" / "tenant-2" / "provider.enc"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(src.read_bytes())
    assert store.load("tenant-2") is None


def test_tampered_ciphertext_returns_none(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr("sk-x")
        ),
        actor="u",
    )
    store.invalidate("tenant-1")
    path = tmp_path / "tenants" / "tenant-1" / "provider.enc"
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 0xFF
    path.write_bytes(bytes(blob))
    assert store.load("tenant-1") is None


@pytest.mark.skipif(sys.platform.startswith("win"), reason="POSIX file mode")
def test_file_mode_is_0o600(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr("sk-x")
        ),
        actor="u",
    )
    path = tmp_path / "tenants" / "tenant-1" / "provider.enc"
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_raw_file_does_not_contain_plaintext_key(tmp_path: Path) -> None:
    secret_key = "sk-leak-canary-9999999999"
    store = RuntimeConfigStore(_settings(tmp_path))
    store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr(secret_key)
        ),
        actor="u",
    )
    path = tmp_path / "tenants" / "tenant-1" / "provider.enc"
    assert secret_key.encode("utf-8") not in path.read_bytes()


def test_status_never_exposes_plaintext_key(tmp_path: Path) -> None:
    secret_key = "sk-also-secret-abcdef"
    store = RuntimeConfigStore(_settings(tmp_path))
    status, _ = store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr(secret_key)
        ),
        actor="u",
    )
    dumped = status.model_dump_json()
    assert secret_key not in dumped


def test_embedding_change_flags_reindex(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    _, reindex_first = store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="fake",
            embedding_provider="hash",
            embedding_dim=384,
        ),
        actor="u",
    )
    assert reindex_first is False  # same as server default

    _, reindex_second = store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="fake",
            embedding_provider="bge-m3",
            embedding_dim=1024,
        ),
        actor="u",
    )
    assert reindex_second is True


@pytest.mark.parametrize(
    "bad_tenant",
    ["", ".", "..", "../foo", "foo/bar", "foo\\bar", "a" * 65, "ten ant", "x\x00y", "."],
)
def test_invalid_tenant_id_is_rejected(tmp_path: Path, bad_tenant: str) -> None:
    """Path traversal / unsafe characters in tenant_id must be refused at every entry point."""

    store = RuntimeConfigStore(_settings(tmp_path))
    with pytest.raises(InvalidTenantIdError):
        store.has_config(bad_tenant)
    with pytest.raises(InvalidTenantIdError):
        store.load(bad_tenant)
    with pytest.raises(InvalidTenantIdError):
        store.status(bad_tenant)
    with pytest.raises(InvalidTenantIdError):
        store.delete(bad_tenant)
    with pytest.raises(InvalidTenantIdError):
        store.save(
            bad_tenant,
            ProviderConfigInput(
                llm_provider="openai", llm_model="m", llm_api_key=SecretStr("sk-x")
            ),
            actor="u",
        )
    # No file should have been created anywhere outside data_dir/tenants/<safe>.
    tenants_root = tmp_path / "tenants"
    if tenants_root.exists():
        for entry in tenants_root.iterdir():
            assert entry.name == bad_tenant or False, (
                f"Unexpected tenant directory created from bad input: {entry}"
            )


def test_delete_removes_file(tmp_path: Path) -> None:
    store = RuntimeConfigStore(_settings(tmp_path))
    store.save(
        "tenant-1",
        ProviderConfigInput(
            llm_provider="openai", llm_model="m", llm_api_key=SecretStr("sk-x")
        ),
        actor="u",
    )
    assert store.delete("tenant-1") is True
    assert store.load("tenant-1") is None
    assert store.delete("tenant-1") is False
