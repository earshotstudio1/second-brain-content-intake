"""
Generic web fetcher using trafilatura.
Used for LinkedIn posts and any URL that isn't Instagram or YouTube.
"""

from __future__ import annotations

from src.fetchers import FAILURE_GUIDANCE, FetchResult


def fetch_generic(url: str, platform: str = "generic") -> FetchResult:
    """Scrape readable text from a URL using trafilatura."""
    import trafilatura

    guidance_key = platform if platform in FAILURE_GUIDANCE else "generic"

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return FetchResult(
                content="",
                source_type=platform,
                partial=True,
                failure_reason="Could not download page content.",
                failure_guidance=FAILURE_GUIDANCE[guidance_key],
            )

        text = trafilatura.extract(downloaded)
        if not text:
            return FetchResult(
                content="",
                source_type=platform,
                partial=True,
                failure_reason="Page downloaded but no readable text could be extracted.",
                failure_guidance=FAILURE_GUIDANCE[guidance_key],
            )

        return FetchResult(
            content=text,
            source_type=platform,
            partial=False,
            failure_reason=None,
            failure_guidance=None,
        )
    except Exception as e:
        return FetchResult(
            content="",
            source_type=platform,
            partial=True,
            failure_reason=f"Scrape error: {e}",
            failure_guidance=FAILURE_GUIDANCE[guidance_key],
        )
