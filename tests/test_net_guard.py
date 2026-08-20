"""
Tests for the outbound request guard.

DNS and HTTP are both mocked. Nothing here touches the network.
"""

import socket
from unittest.mock import patch

import httpx
import pytest

from src.net_guard import UnsafeUrlError, safe_fetch, validate_url


def _addrinfo(*addresses: str):
    """Build a getaddrinfo-shaped result for the given addresses."""
    records = []
    for address in addresses:
        family = socket.AF_INET6 if ":" in address else socket.AF_INET
        sockaddr = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
        records.append((family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr))
    return records


def _dns(*addresses: str):
    """Patch getaddrinfo so every lookup returns the given addresses."""
    return patch("src.net_guard.socket.getaddrinfo", return_value=_addrinfo(*addresses))


class TestSchemeEnforcement:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "gopher://example.com/",
            "data:text/plain,hello",
        ],
    )
    def test_rejects_non_http_schemes(self, url):
        with pytest.raises(UnsafeUrlError, match="http and https"):
            validate_url(url)

    def test_rejects_url_without_hostname(self):
        with pytest.raises(UnsafeUrlError, match="no hostname"):
            validate_url("http:///just-a-path")

    def test_allows_http_and_https_to_a_public_address(self):
        with _dns("93.184.216.34"):
            assert validate_url("http://example.com/a") == "http://example.com/a"
            assert validate_url("https://example.com/a") == "https://example.com/a"


class TestBlockedAddressRanges:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",          # loopback
            "127.53.1.9",         # rest of 127/8
            "0.0.0.0",            # unspecified
            "10.0.0.5",           # RFC1918
            "172.16.4.9",         # RFC1918
            "172.31.255.254",     # RFC1918 upper bound
            "192.168.1.1",        # RFC1918
            "169.254.169.254",    # link-local, cloud metadata
            "::1",                # IPv6 loopback
            "::",                 # IPv6 unspecified
            "fe80::1",            # IPv6 link-local
            "fd00::1",            # IPv6 unique-local
            "fc00::abcd",         # IPv6 unique-local
            "::ffff:127.0.0.1",   # IPv4-mapped loopback
            "::ffff:10.1.2.3",    # IPv4-mapped RFC1918
        ],
    )
    def test_rejects_non_public_addresses(self, address):
        with _dns(address):
            with pytest.raises(UnsafeUrlError, match="Refusing to fetch"):
                validate_url("https://sneaky.example/")

    def test_rejects_when_only_one_of_several_addresses_is_private(self):
        with _dns("93.184.216.34", "10.0.0.7"):
            with pytest.raises(UnsafeUrlError, match="private address"):
                validate_url("https://mixed.example/")

    def test_rejects_literal_private_ip_in_url(self):
        with _dns("192.168.0.10"):
            with pytest.raises(UnsafeUrlError):
                validate_url("http://192.168.0.10:8080/admin")

    def test_rejects_when_dns_fails(self):
        with patch("src.net_guard.socket.getaddrinfo", side_effect=socket.gaierror("nope")):
            with pytest.raises(UnsafeUrlError, match="Could not resolve"):
                validate_url("https://nowhere.example/")

    def test_rejects_when_dns_returns_nothing(self):
        with patch("src.net_guard.socket.getaddrinfo", return_value=[]):
            with pytest.raises(UnsafeUrlError, match="no addresses"):
                validate_url("https://empty.example/")


class TestSafeFetchRedirects:
    def _client_returning(self, responses):
        """Patch httpx.Client so successive GETs return the given responses."""
        calls = []

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def get(self, url, headers=None):
                calls.append(url)
                return responses[len(calls) - 1]

        return patch("httpx.Client", FakeClient), calls

    @staticmethod
    def _redirect(location: str) -> httpx.Response:
        return httpx.Response(302, headers={"location": location})

    @staticmethod
    def _ok(body: str = "<html>hi</html>") -> httpx.Response:
        # raise_for_status needs a request attached to the response.
        return httpx.Response(
            200,
            text=body,
            request=httpx.Request("GET", "https://example.com/"),
        )

    def test_returns_body_when_no_redirects(self):
        client_patch, calls = self._client_returning([self._ok("<html>page</html>")])
        with _dns("93.184.216.34"), client_patch:
            assert safe_fetch("https://example.com/") == "<html>page</html>"
        assert calls == ["https://example.com/"]

    def test_follows_a_safe_redirect(self):
        client_patch, calls = self._client_returning(
            [self._redirect("https://example.org/final"), self._ok("<html>final</html>")]
        )
        with _dns("93.184.216.34"), client_patch:
            assert safe_fetch("https://example.com/") == "<html>final</html>"
        assert calls == ["https://example.com/", "https://example.org/final"]

    def test_blocks_a_redirect_to_a_private_address(self):
        client_patch, _ = self._client_returning(
            [self._redirect("http://169.254.169.254/latest/meta-data/"), self._ok()]
        )
        addresses = {
            "example.com": _addrinfo("93.184.216.34"),
            "169.254.169.254": _addrinfo("169.254.169.254"),
        }
        with patch(
            "src.net_guard.socket.getaddrinfo",
            side_effect=lambda host, *a, **k: addresses[host],
        ), client_patch:
            with pytest.raises(UnsafeUrlError, match="link-local"):
                safe_fetch("https://example.com/")

    def test_blocks_a_redirect_to_a_non_http_scheme(self):
        client_patch, _ = self._client_returning([self._redirect("file:///etc/passwd"), self._ok()])
        with _dns("93.184.216.34"), client_patch:
            with pytest.raises(UnsafeUrlError, match="http and https"):
                safe_fetch("https://example.com/")

    def test_rejects_redirect_without_a_location_header(self):
        client_patch, _ = self._client_returning([httpx.Response(302)])
        with _dns("93.184.216.34"), client_patch:
            with pytest.raises(UnsafeUrlError, match="no Location"):
                safe_fetch("https://example.com/")

    def test_gives_up_after_too_many_redirects(self):
        client_patch, _ = self._client_returning([self._redirect("https://example.com/next")] * 10)
        with _dns("93.184.216.34"), client_patch:
            with pytest.raises(UnsafeUrlError, match="Too many redirects"):
                safe_fetch("https://example.com/", max_redirects=3)


class TestGenericFetcherIntegration:
    def test_blocked_url_becomes_a_partial_failure_result(self):
        from src.fetchers.generic import fetch_generic

        with _dns("127.0.0.1"):
            result = fetch_generic("http://localhost/secret", "generic")

        assert result.partial is True
        assert result.content == ""
        assert "Blocked URL" in result.failure_reason
        assert "private or local address" in result.failure_guidance
