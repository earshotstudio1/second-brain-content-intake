import pytest
from unittest.mock import patch, MagicMock
from src.fetchers.youtube import fetch_youtube


class TestFetchYoutube:
    def test_returns_transcript_text(self):
        fake_transcript = [
            {"text": "Hello world", "start": 0.0, "duration": 1.0},
            {"text": "this is a test", "start": 1.0, "duration": 1.5},
        ]
        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=fake_transcript):
            result = fetch_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.content == "Hello world this is a test"
        assert result.source_type == "youtube"
        assert result.partial is False
        assert result.failure_reason is None

    def test_handles_no_transcript(self):
        from youtube_transcript_api import TranscriptsDisabled
        with patch(
            "youtube_transcript_api.YouTubeTranscriptApi.fetch",
            side_effect=TranscriptsDisabled("dQw4w9WgXcQ"),
        ):
            result = fetch_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.partial is True
        assert result.failure_reason is not None
        assert "transcript" in result.failure_reason.lower()

    def test_extracts_video_id_from_youtu_be(self):
        fake_transcript = [{"text": "short link", "start": 0.0, "duration": 1.0}]
        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", return_value=fake_transcript) as mock:
            fetch_youtube("https://youtu.be/dQw4w9WgXcQ")
        mock.assert_called_once_with("dQw4w9WgXcQ")
