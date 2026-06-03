import pytest
from pathlib import Path
from src.telegram import load_offset, save_offset, parse_messages, TelegramMessage


class TestOffset:
    def test_load_returns_zero_when_file_missing(self, tmp_path):
        assert load_offset(tmp_path / "offset.json") == 0

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "offset.json"
        save_offset(path, 12345)
        assert load_offset(path) == 12345

    def test_save_overwrites_previous(self, tmp_path):
        path = tmp_path / "offset.json"
        save_offset(path, 100)
        save_offset(path, 200)
        assert load_offset(path) == 200


class TestParseMessages:
    def test_parses_text_message(self):
        updates = [
            {
                "update_id": 1,
                "message": {
                    "message_id": 42,
                    "chat": {"id": 999},
                    "text": "hello world",
                },
            }
        ]
        msgs = parse_messages(updates, allowed_chat_id=999)
        assert len(msgs) == 1
        assert msgs[0].message_id == 42
        assert msgs[0].text == "hello world"
        assert msgs[0].voice_file_id is None

    def test_parses_voice_message(self):
        updates = [
            {
                "update_id": 2,
                "message": {
                    "message_id": 43,
                    "chat": {"id": 999},
                    "voice": {"file_id": "file_abc123", "duration": 30},
                },
            }
        ]
        msgs = parse_messages(updates, allowed_chat_id=999)
        assert len(msgs) == 1
        assert msgs[0].voice_file_id == "file_abc123"
        assert msgs[0].text is None

    def test_ignores_messages_from_wrong_chat(self):
        updates = [
            {
                "update_id": 3,
                "message": {
                    "message_id": 44,
                    "chat": {"id": 888},  # wrong chat
                    "text": "not from me",
                },
            }
        ]
        msgs = parse_messages(updates, allowed_chat_id=999)
        assert len(msgs) == 0

    def test_skips_updates_without_message(self):
        updates = [{"update_id": 4}]  # no "message" key
        msgs = parse_messages(updates, allowed_chat_id=999)
        assert len(msgs) == 0
