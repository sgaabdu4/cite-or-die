import socket

import cite_or_die.providers.url_policy as url_policy
from cite_or_die.providers.url_policy import provider_base_url_error, provider_is_hosted


def test_provider_url_policy_allows_docker_host_local_http() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://host.docker.internal:8000/v1",
            allowed_hosts="host.docker.internal",
        )
        is None
    )
    assert (
        provider_base_url_error(
            "ollama",
            "http://host.docker.internal:11434",
            allowed_hosts="host.docker.internal",
        )
        is None
    )


def test_provider_url_policy_classifies_local_and_remote_compatible_hosts() -> None:
    assert (
        provider_is_hosted(
            "openai-compatible",
            "http://localhost:8000/v1",
        )
        is False
    )
    assert (
        provider_is_hosted(
            "openai-compatible",
            "http://host.docker.internal:8000/v1",
            allowed_hosts="host.docker.internal",
        )
        is False
    )
    assert (
        provider_is_hosted(
            "openai-compatible",
            "https://models.example.test/v1",
            allowed_hosts="models.example.test",
        )
        is True
    )
    assert (
        provider_is_hosted(
            "ollama",
            "http://localhost:11434",
        )
        is False
    )
    assert (
        provider_is_hosted(
            "ollama",
            "https://models.example.test",
            allowed_hosts="models.example.test",
        )
        is True
    )


def test_provider_url_policy_restricts_loopback_to_local_provider_ports() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://localhost:9999/v1",
        )
        == "Local provider URL is only allowed over http on provider-specific local ports."
    )
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://localhost:11434/v1",
        )
        == "Local provider URL is only allowed over http on provider-specific local ports."
    )
    assert (
        provider_base_url_error(
            "ollama",
            "http://127.0.0.1:8000",
        )
        == "Local provider URL is only allowed over http on provider-specific local ports."
    )
    assert (
        provider_base_url_error(
            "ollama",
            "https://localhost:11434",
        )
        == "Local provider URL is only allowed over http on provider-specific local ports."
    )
    assert provider_is_hosted("openai-compatible", "http://localhost:9999/v1") is True


def test_provider_url_policy_still_rejects_arbitrary_http_host() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://provider.example/v1",
            allowed_hosts="provider.example",
        )
        == "HTTP base URL is only allowed for localhost providers."
    )


def test_provider_url_policy_rejects_shared_address_space() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "https://100.64.0.1/v1",
            allowed_hosts="100.64.0.1",
        )
        == "Provider base URL cannot target non-public IP addresses."
    )


def test_provider_url_policy_rejects_hostname_resolving_shared_address(
    monkeypatch,
) -> None:
    def shared_dns(hostname: str, port: int | None) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.9", 0))]

    monkeypatch.setattr(url_policy.socket, "getaddrinfo", shared_dns)

    assert (
        provider_base_url_error(
            "openai-compatible",
            "https://provider.example/v1",
            allowed_hosts="provider.example",
        )
        == "Provider base URL cannot resolve to non-public IP addresses."
    )


def test_provider_url_policy_requires_docker_host_allowlist() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://host.docker.internal:8000/v1",
        )
        == "Provider base URL host is not allowlisted."
    )


def test_provider_url_policy_restricts_docker_host_to_local_provider_ports() -> None:
    assert (
        provider_base_url_error(
            "openai-compatible",
            "http://host.docker.internal:11434/v1",
            allowed_hosts="host.docker.internal",
        )
        == "Docker host provider URL is only allowed over http on local provider ports."
    )
    assert (
        provider_base_url_error(
            "ollama",
            "https://host.docker.internal:11434",
            allowed_hosts="host.docker.internal",
        )
        == "Docker host provider URL is only allowed over http on local provider ports."
    )
