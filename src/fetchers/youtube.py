"""YouTube fetcher — uses the free youtube-transcript-api, no API key needed."""

from __future__ import annotations

import re

from src.fetchers import FAILURE_GUIDANCE, FetchResult


def _extract_video_id(url: str) -> str | None:
    """Pull the video ID from any standard YouTube URL format."""
    patterns = [
        r"youtube\.com/watch\?.*v=([^&\s]+)",
        r"youtu\.be/([^?\s]+)",
        r"youtube\.com/shorts/([^?\s]+)",
        r"youtube\.com/embed/([^?\s]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_youtube(url: str) -> FetchResult:
    """Fetch a YouTube video transcript. Returns partial=True if unavailable."""
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

    video_id = _extract_video_id(url)
    if not video_id:
        return FetchResult(
            content="",
            source_type="youtube",
            partial=True,
            failure_reason="Could not extract video ID from URL.",
            failure_guidance=FAILURE_GUIDANCE["youtube"],
        )

    try:
        api = YouTubeTranscriptApi()
        entries = api.fetch(video_id)
        text = " ".join(e["text"] for e in entries)
        return FetchResult(
            content=text,
            source_type="youtube",
            partial=False,
            failure_reason=None,
            failure_guidance=None,
        )
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        return FetchResult(
            content="",
            source_type="youtube",
            partial=True,
            failure_reason=f"No transcript available: {e}",
            failure_guidance=FAILURE_GUIDANCE["youtube"],
        )
    except Exception as e:
        return FetchResult(
            content="",
            source_type="youtube",
            partial=True,
            failure_reason=f"Unexpected error fetching transcript: {e}",
            failure_guidance=FAILURE_GUIDANCE["youtube"],
        )
