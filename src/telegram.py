"""
Telegram Bot API client.
Handles polling for updates, sending replies, and persisting the offset.
All HTTP calls use httpx with a 30-second timeout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

_API_BASE = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 30


@dataclass
class TelegramMessage:
    update_id: int
    message_id: int
    chat_id: int
    text: Optional[str]           # full raw message text (may include a URL)
    voice_file_id: Optional[str]  # set for voice messages


def load_offset(offset_file: Path) -> int:
    """Return the last processed update_id, or 0 if the file doesn't exist."""
    if not offset_file.exists():
        return 0
    try:
        data = json.loads(offset_file.read_text(encoding="utf-8"))
        return int(data.get("offset", 0))
    except (json.JSONDecodeError, ValueError):
        return 0


def save_offset(offset_file: Path, offset: int) -> None:
    """Persist the current offset so the next run doesn't re-process messages."""
    offset_file.write_text(
        json.dumps({"offset": offset}), encoding="utf-8"
    )


def get_updates(token: str, offset: int) -> list[dict]:
    """
    Fetch new updates from the Telegram Bot API.
    Returns a (possibly empty) list of update dicts.
    Uses offset+1 so already-processed updates are not returned.
    """
    url = _API_BASE.format(token=token, method="getUpdates")
    params = {"offset": offset + 1, "timeout": 0}
    response = httpx.get(url, params=params, timeout=_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getUpdates error: {data}")
    return data.get("result", [])


def send_reply(token: str, chat_id: int, text: str) -> None:
    """Send a text reply to the user."""
    url = _API_BASE.format(token=token, method="sendMessage")
    response = httpx.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram sendMessage error: {data}")


def get_file_url(token: str, file_id: str) -> str:
    """Resolve a Telegram file_id to a download URL."""
    url = _API_BASE.format(token=token, method="getFile")
    response = httpx.get(url, params={"file_id": file_id}, timeout=_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram getFile error: {data}")
    file_path = data["result"]["file_path"]
    return f"https://api.telegram.org/file/bot{token}/{file_path}"


def parse_messages(updates: list[dict], allowed_chat_id: int) -> list[TelegramMessage]:
    """
    Extract TelegramMessage objects from raw update dicts.
    Silently drops messages from any chat other than allowed_chat_id.
    """
    messages = []
    for update in updates:
        msg = update.get("message")
        if not msg:
            continue

        chat_id = msg.get("chat", {}).get("id")
        if chat_id != allowed_chat_id:
            continue

        voice = msg.get("voice")
        messages.append(
            TelegramMessage(
                update_id=update["update_id"],
                message_id=msg["message_id"],
                chat_id=chat_id,
                text=msg.get("text"),
                voice_file_id=voice["file_id"] if voice else None,
            )
        )
    return messages
