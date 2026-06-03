"""
Instagram fetcher.
Strategy:
  1. yt-dlp downloads the video to a temp file.
  2. Gemini Files API analyses the video content.
  3. If yt-dlp fails, fall back to trafilatura caption scrape.
  4. If both fail, return a partial FetchResult with guidance.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from src.fetchers import FAILURE_GUIDANCE, FetchResult
from src.fetchers.generic import fetch_generic

if TYPE_CHECKING:
    from src.config import ModelConfig

_VIDEO_ANALYSIS_PROMPT = """\
Watch this video and extract the following:
1. The main message or lesson being communicated
2. Key points or tips mentioned (bullet list)
3. Any specific tactics, frameworks, or tools referenced

Be concise. Focus on actionable content. Return plain text, no markdown headers.\
"""


def _download_with_ytdlp(url: str, output_path: str) -> bool:
    """
    Attempt to download a video using yt-dlp.
    Returns True on success, False if yt-dlp fails or is not available.
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "mp4/best[ext=mp4]/best",  # prefer mp4
                "-o", output_path,
                "--quiet",
                "--no-warnings",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0 and Path(output_path).exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _analyse_video_with_gemini(video_path: Path, model_config: "ModelConfig") -> str:
    """Upload video to Gemini Files API and return the analysis text."""
    from src.llm import call_llm_with_video
    return call_llm_with_video(model_config, _VIDEO_ANALYSIS_PROMPT, video_path)


def fetch_instagram(url: str, model_config: "ModelConfig") -> FetchResult:
    """
    Fetch Instagram Reel content.
    Tries yt-dlp + Gemini video analysis first, falls back to trafilatura.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = str(Path(tmpdir) / "reel.mp4")
        downloaded = _download_with_ytdlp(url, video_path)

        if downloaded:
            try:
                analysis = _analyse_video_with_gemini(Path(video_path), model_config)
                return FetchResult(
                    content=analysis,
                    source_type="instagram",
                    partial=False,
                    failure_reason=None,
                    failure_guidance=None,
                )
            except Exception:
                pass  # fall through to caption scrape

    # Fallback: trafilatura caption scrape
    caption_result = fetch_generic(url, platform="instagram")
    if not caption_result.partial:
        return FetchResult(
            content=caption_result.content,
            source_type="instagram",
            partial=True,
            failure_reason="Video download succeeded but analysis failed, or video unavailable. Caption text only.",
            failure_guidance=None,
        )

    # Full failure
    return FetchResult(
        content="",
        source_type="instagram",
        partial=True,
        failure_reason="Could not download video or scrape caption.",
        failure_guidance=FAILURE_GUIDANCE["instagram"],
    )
