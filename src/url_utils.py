"""
URL extraction and platform detection utilities.
Pure functions — no side effects, no I/O.
"""

from __future__ import annotations
import re

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


def detect_platform(url: str | None) -> str:
    """
    Identify the platform from a URL.
    Returns: 'instagram' | 'youtube' | 'linkedin' | 'generic'
    """
    if not url:
        return "generic"

    url_lower = url.lower()

    if "instagram.com" in url_lower:
        return "instagram"

    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"

    if "linkedin.com" in url_lower:
        return "linkedin"

    return "generic"
