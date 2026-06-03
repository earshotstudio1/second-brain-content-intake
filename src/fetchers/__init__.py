"""
Content fetchers — one module per platform.

Each fetcher returns a FetchResult. The dispatcher fetch_url() routes
to the correct fetcher based on platform string from url_utils.detect_platform().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import ModelConfig

FAILURE_GUIDANCE: dict[str, str] = {
    "instagram": (
        "Instagram blocked the download. "
        "Paste the caption text directly and resend."
    ),
    "youtube": (
        "This video has no transcript (captions may be disabled). "
        "Send a summary in your own words."
    ),
    "linkedin": (
        "LinkedIn requires login to scrape. "
        "Paste the post text directly and resend."
    ),
    "generic": (
        "Couldn't read content from this URL. "
        "Paste the relevant text directly."
    ),
    "voice": (
        "Could not process voice note. "
        "Try re-recording or send as text. "
        "Audio has been saved to Untranscribed/ for manual review."
    ),
}


@dataclass
class FetchResult:
    content: str                       # extracted text (may be empty on full failure)
    source_type: str                   # "instagram" | "youtube" | "linkedin" | "generic" | "text" | "voice"
    partial: bool                      # True if only partial content was retrieved
    failure_reason: Optional[str]      # short description of what went wrong
    failure_guidance: Optional[str]    # user-facing next-step instruction


def fetch_url(url: str, platform: str, model_config: "ModelConfig") -> "FetchResult":
    """Dispatch a URL to the correct fetcher based on platform."""
    if platform == "youtube":
        from src.fetchers.youtube import fetch_youtube
        return fetch_youtube(url)

    if platform == "instagram":
        from src.fetchers.instagram import fetch_instagram
        return fetch_instagram(url, model_config)

    from src.fetchers.generic import fetch_generic
    return fetch_generic(url, platform)
