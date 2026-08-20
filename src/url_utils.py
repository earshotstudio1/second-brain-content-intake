"""
URL extraction and platform detection utilities.
Pure functions — no side effects, no I/O.
"""

from __future__ import annotations
import re
from urllib.parse import urlparse

# Matches http(s):// URLs — permissive enough to catch most real-world URLs
_URL_PATTERN = re.compile(r"https?://[^\s\]>\"']+")


def extract_url(text: str) -> str | None:
    """Return the first URL found in text, or None if there is none."""
    if not text:
        return None
    match = _URL_PATTERN.search(text)
    return match.group(0).rstrip(".,;)") if match else None


def extract_context(text: str, url: str | None) -> str:
    """Return the text with the URL removed and whitespace collapsed."""
    if url is None:
        return text
    return text.replace(url, "").strip()


def _hostname(url: str) -> str:
    """Return the lowercased hostname of a URL, or '' if it has none."""
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_host(host: str, domain: str) -> bool:
    """True if host is domain itself or a subdomain of it.

    Substring checks are not safe here: "instagram.com" appears in both
    instagram.com.attacker.example and example.com/?next=instagram.com, and
    routing either of those to the authenticated Instagram fetcher would send
    credentials to a host we do not control.
    """
    return host == domain or host.endswith("." + domain)


def detect_platform(url: str | None) -> str:
    """
    Identify the platform from a URL.
    Returns: 'instagram' | 'youtube' | 'linkedin' | 'generic'
    """
    if not url:
        return "generic"

    host = _hostname(url)
    if not host:
        return "generic"

    if _is_host(host, "instagram.com"):
        return "instagram"

    if _is_host(host, "youtube.com") or _is_host(host, "youtu.be"):
        return "youtube"

    if _is_host(host, "linkedin.com"):
        return "linkedin"

    return "generic"
