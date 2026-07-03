import socket

import httpcore
import httpx
import pytest

import cite_or_die.api.app as app_module
import cite_or_die.providers.network as provider_network
from cite_or_die.providers.network import GuardedAsyncNetworkBackend


class _FakeStream(httpcore.AsyncNetworkStream):
    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:  # noqa: ASYNC109
        return b""

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:  # noqa: ASYNC109
        return None

    async def aclose(self) -> None:
        return None

    async def start_tls(  # noqa: ASYNC109
        self,
        ssl_context,
        server_hostname: str | None = None,
        timeout: float | None = None,  # noqa: ASYNC109
    ) -> httpcore.AsyncNetworkStream:
        return self

    def get_extra_info(self, info: str):
        return None


class _CapturingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(  # noqa: ASYNC109
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        self.hosts.append(host)
        return _FakeStream()

    async def connect_unix_socket(  # noqa: ASYNC109
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        return _FakeStream()

    async def sleep(self, seconds: float) -> None:
        return None


@pytest.mark.asyncio()
async def test_guarded_network_backend_pins_public_resolution(monkeypatch) -> None:
    inner = _CapturingBackend()

    def public_dns(hostname: str, port: int, type: int = 0) -> list:
        assert hostname == "provider.example"
        assert port == 443
        assert type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(provider_network.socket, "getaddrinfo", public_dns)

    backend = GuardedAsyncNetworkBackend(inner=inner)
    await backend.connect_tcp("provider.example", 443)

    assert inner.hosts == ["93.184.216.34"]


@pytest.mark.asyncio()
async def test_guarded_network_backend_rejects_private_resolution(monkeypatch) -> None:
    inner = _CapturingBackend()

    def private_dns(hostname: str, port: int, type: int = 0) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.9", port))]

    monkeypatch.setattr(provider_network.socket, "getaddrinfo", private_dns)

    backend = GuardedAsyncNetworkBackend(inner=inner)
    with pytest.raises(httpcore.ConnectError, match="non-public"):
        await backend.connect_tcp("provider.example", 443)

    assert inner.hosts == []


@pytest.mark.asyncio()
async def test_guarded_network_backend_rejects_shared_address_resolution(
    monkeypatch,
) -> None:
    inner = _CapturingBackend()

    def shared_dns(hostname: str, port: int, type: int = 0) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("100.64.0.9", port))]

    monkeypatch.setattr(provider_network.socket, "getaddrinfo", shared_dns)

    backend = GuardedAsyncNetworkBackend(inner=inner)
    with pytest.raises(httpcore.ConnectError, match="non-public"):
        await backend.connect_tcp("provider.example", 443)

    assert inner.hosts == []


@pytest.mark.asyncio()
async def test_guarded_network_backend_allows_explicit_local_provider() -> None:
    inner = _CapturingBackend()
    backend = GuardedAsyncNetworkBackend(allow_local_addresses=True, inner=inner)

    await backend.connect_tcp("localhost", 8000)

    assert inner.hosts == ["localhost"]


@pytest.mark.asyncio()
async def test_provider_probe_uses_guarded_transport(monkeypatch) -> None:
    guarded_urls: list[str] = []

    def guarded_transport(url: str) -> httpx.AsyncBaseTransport:
        guarded_urls.append(url)

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        return httpx.MockTransport(handler)

    monkeypatch.setattr(app_module, "safe_async_transport_for_url", guarded_transport)

    await app_module._post_provider_test_json(
        "https://provider.example/v1/chat/completions",
        {},
        {"model": "model-a"},
    )

    assert guarded_urls == ["https://provider.example/v1/chat/completions"]
