from __future__ import annotations

import socket
from collections.abc import AsyncIterable, Iterable
from ipaddress import ip_address
from typing import cast
from urllib.parse import urlparse

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend
from httpcore._backends.base import SOCKET_OPTION, AsyncNetworkBackend, AsyncNetworkStream
from httpx._transports.default import AsyncResponseStream, map_httpcore_exceptions

from cite_or_die.providers.url_policy import is_blocked_address, is_docker_host, is_loopback_host

_BLOCKED_RESOLUTION = "Provider base URL cannot resolve to non-public IP addresses."
_LOCAL_PROVIDER_PORTS = {8000, 11434}


def safe_async_transport_for_url(url: str) -> httpx.AsyncBaseTransport:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    allow_local = (
        parsed.scheme == "http"
        and port in _LOCAL_PROVIDER_PORTS
        and (is_loopback_host(hostname) or is_docker_host(hostname))
    )
    return GuardedAsyncHTTPTransport(allow_local_addresses=allow_local)


class GuardedAsyncHTTPTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, allow_local_addresses: bool = False) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            network_backend=GuardedAsyncNetworkBackend(
                allow_local_addresses=allow_local_addresses
            )
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)
        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(cast(AsyncIterable[bytes], resp.stream)),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


class GuardedAsyncNetworkBackend(AsyncNetworkBackend):
    def __init__(
        self,
        *,
        allow_local_addresses: bool = False,
        inner: AsyncNetworkBackend | None = None,
    ) -> None:
        self._allow_local_addresses = allow_local_addresses
        self._inner = inner or AutoBackend()

    async def connect_tcp(  # noqa: ASYNC109
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109
        local_address: str | None = None,
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        addresses = self._connect_addresses(host, port)
        last_error: httpcore.ConnectError | httpcore.ConnectTimeout | None = None
        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("Provider host did not resolve.")

    async def connect_unix_socket(  # noqa: ASYNC109
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109
        socket_options: Iterable[SOCKET_OPTION] | None = None,
    ) -> AsyncNetworkStream:
        return await self._inner.connect_unix_socket(
            path,
            timeout=timeout,
            socket_options=socket_options,
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)

    def _connect_addresses(self, host: str, port: int) -> list[str]:
        hostname = host.strip().rstrip(".").lower()
        if self._allow_local_addresses and (
            is_loopback_host(hostname) or is_docker_host(hostname)
        ):
            return [host]
        try:
            address = ip_address(hostname)
        except ValueError:
            return _resolved_public_addresses(hostname, port)
        if is_blocked_address(str(address)):
            raise httpcore.ConnectError(_BLOCKED_RESOLUTION)
        return [str(address)]


def _resolved_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise httpcore.ConnectError(str(exc)) from exc
    addresses: list[str] = []
    for record in records:
        address = str(record[4][0])
        if is_blocked_address(address):
            raise httpcore.ConnectError(_BLOCKED_RESOLUTION)
        if address not in addresses:
            addresses.append(address)
    return addresses
