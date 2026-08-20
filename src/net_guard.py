"""
Outbound request guard.

Anything the intake pipeline fetches from the open web goes through here first.
The point is to stop a captured URL from reaching machines that are not on the
public internet: the local host, the home or office LAN, cloud metadata
endpoints, and the IPv6 equivalents of all three. Redirects are followed by hand
so that every hop is checked, not just the first one.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse, urlunparse

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Follow at most this many redirects before giving up.
MAX_REDIRECTS = 5

# Seconds to wait on connect and read.
REQUEST_TIMEOUT = 15.0

# Refuse anything larger than this so a hostile page cannot exhaust memory.
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

_USER_AGENT = "second-brain-content-intake/1.0"


class UnsafeUrlError(ValueError):
    """Raised when a URL points somewhere the fetcher is not allowed to go."""


def _blocked_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Return a human-readable reason if this address is off limits, else None."""
    # An IPv4 address tunnelled inside IPv6 is judged on its IPv4 value.
    if isinstance(ip, ipaddress.IPv6Address):
        mapped = ip.ipv4_mapped
        if mapped is None and ip.sixtofour is not None:
            mapped = ip.sixtofour
        if mapped is not None:
            inner = _blocked_reason(mapped)
            return inner if inner is None else f"IPv4-in-IPv6 address ({inner})"

    if ip.is_unspecified:
        return "unspecified address"
    if ip.is_loopback:
        return "loopback address"
    if ip.is_link_local:
        return "link-local address"
    if ip.is_multicast:
        return "multicast address"
    if isinstance(ip, ipaddress.IPv6Address) and ip.is_site_local:
        return "site-local address"
    # fc00::/7 unique-local, plus RFC1918 10/8, 172.16/12 and 192.168/16.
    if ip.is_private:
        return "private address"
    if ip.is_reserved:
        return "reserved address"
    return None


def resolve_host(host: str, port: int) -> list[str]:
    """Resolve a hostname to every address it maps to. Raises UnsafeUrlError on failure."""
    try:
        records = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve host '{host}': {exc}") from exc
    if not records:
        raise UnsafeUrlError(f"Host '{host}' resolved to no addresses.")
    seen: list[str] = []
    for record in records:
        address = record[4][0]
        if address not in seen:
            seen.append(address)
    return seen


def check_addresses(addresses: Iterable[str], host: str) -> None:
    """Raise UnsafeUrlError if any resolved address is not a public one."""
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise UnsafeUrlError(f"Host '{host}' resolved to an unusable address.") from exc
        reason = _blocked_reason(ip)
        if reason is not None:
            raise UnsafeUrlError(
                f"Refusing to fetch '{host}': it resolves to a {reason} ({address})."
            )


def validate_url(url: str) -> str:
    """
    Check a single URL and return it normalised.

    Enforces http/https, requires a hostname, and resolves that hostname so the
    real destination is judged rather than the text of the URL.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(
            f"Only http and https URLs are allowed, got '{parsed.scheme or url}'."
        )

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL has no hostname.")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrlError("URL has an invalid port.") from exc

    check_addresses(resolve_host(host, port), host)
    return urlunparse(parsed)


def safe_fetch(
    url: str,
    max_redirects: int = MAX_REDIRECTS,
    timeout: float = REQUEST_TIMEOUT,
) -> str:
    """
    Fetch a URL as text with every redirect hop validated.

    Returns the response body. Raises UnsafeUrlError if the starting URL or any
    hop points somewhere private, or if the redirect budget runs out.
    """
    import httpx

    current = validate_url(url)

    with httpx.Client(follow_redirects=False, timeout=timeout) as client:
        for _ in range(max_redirects + 1):
            response = client.get(current, headers={"User-Agent": _USER_AGENT})

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise UnsafeUrlError("Redirect response had no Location header.")
                # Resolve relative redirects against the hop we are on.
                current = validate_url(str(httpx.URL(current).join(location)))
                continue

            response.raise_for_status()
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise UnsafeUrlError("Response body was larger than the allowed limit.")
            return response.text

    raise UnsafeUrlError(f"Too many redirects (limit {max_redirects}).")
