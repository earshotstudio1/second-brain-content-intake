"""
Voice note transcriber.
Downloads a Telegram .ogg voice file, converts it to mp3 via pydub/ffmpeg,
and sends it to the OpenAI Whisper API for transcription.

Requires ffmpeg installed and available on PATH.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx


def download_voice(file_url: str) -> Path:
    """
    Download a Telegram voice file to a temp .ogg file.
    Returns the path to the downloaded file.
    The caller is responsible for cleanup.
    """
    response = httpx.get(file_url, timeout=60, follow_redirects=True)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
    tmp.write(response.content)
    tmp.close()
    return Path(tmp.name)


def _convert_ogg_to_mp3(ogg_path: Path) -> Path:
    """Convert .ogg to .mp3 using pydub. Returns path to the .mp3 file."""
    from pydub import AudioSegment

    mp3_path = ogg_path.with_suffix(".mp3")
    audio = AudioSegment.from_ogg(str(ogg_path))
    audio.export(str(mp3_path), format="mp3")
    return mp3_path


def transcribe_voice(ogg_path: Path, openai_api_key: str) -> str:
    """
    Convert the .ogg file to mp3 and transcribe via OpenAI Whisper.
    Returns the transcript text.
    """
    import openai

    mp3_path = _convert_ogg_to_mp3(ogg_path)
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        with open(mp3_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
            )
        return transcript.text.strip()
    finally:
        mp3_path.unlink(missing_ok=True)
