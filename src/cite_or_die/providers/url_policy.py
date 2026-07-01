from __future__ import annotations

import socket
from collections.abc import Iterable
from ipaddress import ip_address
from urllib.parse import urlparse

_BLOCKED_TARGET = "Provider base URL cannot target private or link-local IP addresses."
_BLOCKED_RESOLUTION = "Provider base URL cannot resolve to private or link-local IP addresses."
_HTTP_REMOTE = "HTTP base URL is only allowed for localhost providers."
_INVALID_URL = "Base URL must be an http(s) URL without credentials."
_MISSING_URL = "Base URL required."
_NOT_ALLOWED = "Provider base URL host is not allowlisted."


def provider_base_url_error(
    provider: str,
    base_url: str,
    allowed_hosts: str | Iterable[str] = "",
) -> str | None:
    if provider not in {"openai-compatible", "ollama"}:
        return None
    if not base_url:
        return _MISSING_URL
    parsed = urlparse(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        return _INVALID_URL
    hostname = _normalise_hostname(parsed.hostname)
    if is_loopback_host(hostname):
        return None
    if parsed.scheme == "http":
        return _HTTP_REMOTE
    try:
        address = ip_address(hostname)
    except ValueError:
        if hostname not in parse_allowed_hosts(allowed_hosts):
            return _NOT_ALLOWED
        if hostname_resolves_to_blocked_address(hostname):
            return _BLOCKED_RESOLUTION
        return None
    if is_blocked_address(str(address)):
        return _BLOCKED_TARGET
    if hostname not in parse_allowed_hosts(allowed_hosts):
        return _NOT_ALLOWED
    return None


def parse_allowed_hosts(allowed_hosts: str | Iterable[str]) -> set[str]:
    if isinstance(allowed_hosts, str):
        values: Iterable[str] = allowed_hosts.split(",")
    else:
        values = allowed_hosts
    return {_normalise_hostname(value) for value in values if value.strip()}


def hostname_resolves_to_blocked_address(hostname: str) -> bool:
    try:
        records = socket.getaddrinfo(hostname, None)
    except OSError:
        return False
    for record in records:
        if is_blocked_address(str(record[4][0])):
            return True
    return False


def is_loopback_host(hostname: str) -> bool:
    lowered = _normalise_hostname(hostname)
    if lowered == "localhost":
        return True
    try:
        return ip_address(lowered).is_loopback
    except ValueError:
        return False


def is_blocked_address(value: str) -> bool:
    try:
        address = ip_address(value)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _normalise_hostname(hostname: str) -> str:
    return hostname.strip().rstrip(".").lower()
