# Telegram Capture Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot capture pipeline that receives URLs, text, and voice notes from the user's phone, processes them with Gemini Flash (free) and Whisper (voice only), and files structured notes into the Obsidian vault — with a bot reply confirming every outcome.

**Architecture:** `capture.py` is the entry point, fired every 5 minutes by Windows Task Scheduler. It polls Telegram for new messages, routes each one through a fetcher (YouTube transcript API / yt-dlp+Gemini for Instagram / trafilatura for generic / Whisper for voice), classifies the content via Gemini Flash into one of four vault folders (Captures / Ideas / Knowledge / Inbox), writes a structured Markdown note, and sends a reply to the user. The pipeline extends the existing `second-brain v1` project, reusing `src/config.py`, `src/llm.py`, `src/tracker.py`, and `src/writer.py` patterns throughout.

**Tech Stack:** Python 3.13, google-generativeai (Gemini Flash free tier), yt-dlp, youtube-transcript-api, trafilatura, pydub + ffmpeg, httpx, OpenAI Whisper API (voice only), Telegram Bot API (polling via httpx)

---

## File Map

**Create:**
- `capture.py` — entry point, orchestrates the pipeline
- `src/url_utils.py` — URL extraction and platform detection from message text
- `src/telegram.py` — Telegram polling, reply sending, offset persistence
- `src/transcriber.py` — voice note download (.ogg → mp3) and Whisper transcription
- `src/classifier.py` — Gemini Flash classification, `ClassifiedCapture` dataclass
- `src/capture_writer.py` — write structured notes to correct vault folder
- `src/fetchers/__init__.py` — `fetch_url()` dispatcher + `FetchResult` dataclass
- `src/fetchers/youtube.py` — youtube-transcript-api extraction
- `src/fetchers/instagram.py` — yt-dlp download + Gemini video analysis + trafilatura fallback
- `src/fetchers/generic.py` — trafilatura scrape for LinkedIn and other URLs
- `tests/__init__.py` — empty
- `tests/test_url_utils.py` — platform detection and URL parsing tests
- `tests/test_classifier.py` — JSON parsing and ClassifiedCapture construction tests
- `tests/test_capture_writer.py` — note formatting and file placement tests
- `tests/test_telegram.py` — offset file read/write tests

**Modify:**
- `src/config.py` — add `google` provider, `CaptureConfig` dataclass, `load_capture_config()`
- `src/llm.py` — add Gemini provider, `call_llm_with_video()` for Instagram Reels
- `config.yaml` — add `telegram`, `capture_folders`, `models.capture_processing` sections
- `.env.example` — add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GOOGLE_API_KEY`
- `requirements.txt` — add new dependencies

---

## Task 1: Project setup — config, env, dependencies

**Files:**
- Modify: `config.yaml`
- Modify: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 1: Update `config.yaml`** — append the new sections after the existing `models:` block

Open `config.yaml` and replace the entire file with:

```yaml
# Second Brain — Configuration

vault_path: "C:/Users/user/vault"

# Where you drop raw transcript files
input_folder: "Transcripts"

# Where processed notes are written (auto-created if absent)
output_folder: "Meetings"

# Processed-file tracking log — do not edit manually
tracking_file: ".second-brain/processed.jsonl"

# File extensions to scan for transcripts
supported_extensions:
  - ".txt"
  - ".md"
  - ".vtt"
  - ".srt"

# Telegram capture pipeline
telegram:
  offset_file: ".second-brain/telegram_offset.json"

# Vault folders for captured content (auto-created on first run)
capture_folders:
  captures: "Captures"
  ideas: "Ideas"
  knowledge: "Knowledge"
  inbox: "Inbox"

# Model configuration
models:
  transcript_processing:
    provider: openai
    model: gpt-4o-mini

  capture_processing:
    provider: google
    model: gemini-2.0-flash
```

- [ ] **Step 2: Update `.env.example`**

Replace the contents of `.env.example` with:

```
# LLM providers — add the key(s) for whichever provider(s) you use
ANTHROPIC_API_KEY=your-anthropic-key-here
OPENAI_API_KEY=your-openai-key-here

# Gemini (free tier — used for capture_processing)
GOOGLE_API_KEY=your-google-ai-studio-key-here

# Telegram bot (capture pipeline)
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather
TELEGRAM_CHAT_ID=your-personal-numeric-chat-id
```

- [ ] **Step 3: Update `requirements.txt`**

Replace with:

```
anthropic>=0.40.0
openai>=1.0.0
python-dotenv>=1.0.0
pyyaml>=6.0
google-generativeai>=0.8.0
yt-dlp>=2024.1.0
youtube-transcript-api>=0.6.0
trafilatura>=1.6.0
pydub>=0.25.0
httpx>=0.27.0
pytest>=8.0.0
```

- [ ] **Step 4: Install new dependencies**

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Expected: all packages install without errors. `yt-dlp --version` should print a version number.

- [ ] **Step 5: Commit**

```bash
git add config.yaml .env.example requirements.txt
git commit -m "chore: add capture pipeline config, env vars, and dependencies"
```

---

## Task 2: Extend config.py — CaptureConfig and Google provider

**Files:**
- Modify: `src/config.py`

- [ ] **Step 1: Write failing test**

Create `tests/__init__.py` (empty file), then create `tests/test_config.py`:

```python
import os
import pytest
from pathlib import Path
from unittest.mock import patch


def test_google_provider_requires_google_api_key(tmp_path):
    """CaptureConfig raises EnvironmentError if GOOGLE_API_KEY is missing."""
    from src.config import _load_model_config
    raw_models = {"capture_processing": {"provider": "google", "model": "gemini-2.0-flash"}}
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(EnvironmentError, match="GOOGLE_API_KEY"):
            _load_model_config("capture_processing", raw_models)


def test_google_provider_loads_with_key(tmp_path):
    """CaptureConfig loads correctly when GOOGLE_API_KEY is set."""
    from src.config import _load_model_config
    raw_models = {"capture_processing": {"provider": "google", "model": "gemini-2.0-flash"}}
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}):
        cfg = _load_model_config("capture_processing", raw_models)
    assert cfg.provider == "google"
    assert cfg.model == "gemini-2.0-flash"
    assert cfg.api_key == "fake-key"
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL — `google` is not in `_PROVIDER_ENV`.

- [ ] **Step 3: Update `src/config.py`**

Replace the entire file:

```python
"""
Configuration loader.
Reads config.yaml and environment variables, validates paths, creates
vault directories if they don't already exist.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_FILE = Path(__file__).parent.parent / "config.yaml"

# Maps provider name → expected environment variable name.
_PROVIDER_ENV: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
}


@dataclass
class ModelConfig:
    """Holds everything needed to make a single LLM call."""
    provider: str
    model: str
    api_key: str


@dataclass
class CaptureConfig:
    """Settings for the Telegram capture pipeline."""
    telegram_token: str
    telegram_chat_id: int
    offset_file: Path
    capture_folders: Dict[str, Path]  # category -> absolute vault path
    capture_model: ModelConfig


@dataclass
class Config:
    vault_path: Path
    input_dir: Path
    output_dir: Path
    tracking_file: Path
    supported_extensions: List[str]
    models: Dict[str, ModelConfig]


def _load_model_config(workflow: str, raw_models: dict) -> ModelConfig:
    """Parse and validate one workflow entry from the models: section."""
    entry = raw_models.get(workflow)
    if not entry:
        raise ValueError(
            f"models.{workflow} is not configured in config.yaml. "
            f"Add a provider and model for it."
        )

    provider = str(entry.get("provider", "")).strip().lower()
    model = str(entry.get("model", "")).strip()

    if not provider:
        raise ValueError(f"models.{workflow}.provider is required in config.yaml")
    if not model:
        raise ValueError(f"models.{workflow}.model is required in config.yaml")

    env_var = _PROVIDER_ENV.get(provider)
    if env_var is None:
        raise ValueError(
            f"models.{workflow}.provider is {provider!r}, which is not supported. "
            f"Supported providers: {', '.join(_PROVIDER_ENV)}"
        )

    api_key = os.environ.get(env_var, "").strip()
    if not api_key:
        raise EnvironmentError(
            f"{env_var} is not set. "
            f"Add it to your .env file (required for provider '{provider}', "
            f"used by models.{workflow})."
        )

    return ModelConfig(provider=provider, model=model, api_key=api_key)


def load_config() -> Config:
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"config.yaml not found at {_CONFIG_FILE}. "
            "Copy config.yaml.example to config.yaml and edit it."
        )

    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    vault_path = Path(raw["vault_path"])
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")

    input_dir = vault_path / raw["input_folder"]
    output_dir = vault_path / raw["output_folder"]
    tracking_file = vault_path / raw["tracking_file"]

    output_dir.mkdir(parents=True, exist_ok=True)
    tracking_file.parent.mkdir(parents=True, exist_ok=True)

    raw_models = raw.get("models", {})
    models = {
        "transcript_processing": _load_model_config("transcript_processing", raw_models),
    }

    return Config(
        vault_path=vault_path,
        input_dir=input_dir,
        output_dir=output_dir,
        tracking_file=tracking_file,
        supported_extensions=raw.get("supported_extensions", [".txt"]),
        models=models,
    )


def load_capture_config() -> CaptureConfig:
    """Load Telegram capture pipeline config. Call only from capture.py."""
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(f"config.yaml not found at {_CONFIG_FILE}")

    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    vault_path = Path(raw["vault_path"])
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")

    tg = raw.get("telegram", {})
    offset_file = vault_path / tg.get("offset_file", ".second-brain/telegram_offset.json")
    offset_file.parent.mkdir(parents=True, exist_ok=True)

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not telegram_token:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN is not set. Add it to your .env file.")

    chat_id_str = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id_str:
        raise EnvironmentError("TELEGRAM_CHAT_ID is not set. Add it to your .env file.")
    telegram_chat_id = int(chat_id_str)

    raw_folders = raw.get("capture_folders", {})
    capture_folders: Dict[str, Path] = {}
    for category, folder_name in raw_folders.items():
        folder_path = vault_path / folder_name
        folder_path.mkdir(parents=True, exist_ok=True)
        capture_folders[category] = folder_path

    raw_models = raw.get("models", {})
    capture_model = _load_model_config("capture_processing", raw_models)

    return CaptureConfig(
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
        offset_file=offset_file,
        capture_folders=capture_folders,
        capture_model=capture_model,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_config.py -v
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/__init__.py tests/test_config.py
git commit -m "feat(config): add google provider, CaptureConfig, load_capture_config"
```

---

## Task 3: Add Gemini to llm.py

**Files:**
- Modify: `src/llm.py`

- [ ] **Step 1: Replace `src/llm.py`**

```python
"""
LLM provider router.
Supports: anthropic, openai, google (Gemini)

To add a new provider:
  1. Add it to _PROVIDER_ENV in config.py
  2. Add an elif branch here
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import ModelConfig

try:
    import anthropic as _anthropic_sdk
except ImportError:
    _anthropic_sdk = None  # type: ignore[assignment]

try:
    import openai as _openai_sdk
except ImportError:
    _openai_sdk = None  # type: ignore[assignment]

try:
    import google.generativeai as _genai
except ImportError:
    _genai = None  # type: ignore[assignment]


def call_llm(model_config: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    """Route an LLM call to the correct provider. Returns the response text."""
    if model_config.provider == "anthropic":
        return _call_anthropic(model_config, system_prompt, user_prompt)
    elif model_config.provider == "openai":
        return _call_openai(model_config, system_prompt, user_prompt)
    elif model_config.provider == "google":
        return _call_google(model_config, system_prompt, user_prompt)
    else:
        raise ValueError(
            f"Unknown provider {model_config.provider!r}. "
            "Supported providers: anthropic, openai, google"
        )


def call_llm_with_video(model_config: "ModelConfig", prompt: str, video_path: Path) -> str:
    """Analyse a local video file using Gemini's multimodal capability.

    Only supported for provider='google'. Uploads the file to the Gemini
    Files API, waits for processing, then generates content.
    """
    if model_config.provider != "google":
        raise ValueError(
            f"call_llm_with_video requires provider='google', got {model_config.provider!r}"
        )
    if _genai is None:
        raise ImportError("The 'google-generativeai' package is not installed. Run: pip install google-generativeai")

    _genai.configure(api_key=model_config.api_key)

    video_file = _genai.upload_file(path=str(video_path), mime_type="video/mp4")

    # Poll until the file is ready
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = _genai.get_file(video_file.name)

    if video_file.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini file processing failed with state: {video_file.state.name}")

    model = _genai.GenerativeModel(model_config.model)
    response = model.generate_content([prompt, video_file])

    # Clean up the uploaded file
    _genai.delete_file(video_file.name)

    return response.text.strip()


def _call_anthropic(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _anthropic_sdk is None:
        raise ImportError("The 'anthropic' package is not installed. Run: pip install anthropic")
    client = _anthropic_sdk.Anthropic(api_key=cfg.api_key)
    response = client.messages.create(
        model=cfg.model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


def _call_openai(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _openai_sdk is None:
        raise ImportError("The 'openai' package is not installed. Run: pip install openai")
    client = _openai_sdk.OpenAI(api_key=cfg.api_key)
    response = client.chat.completions.create(
        model=cfg.model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _call_google(cfg: "ModelConfig", system_prompt: str, user_prompt: str) -> str:
    if _genai is None:
        raise ImportError("The 'google-generativeai' package is not installed. Run: pip install google-generativeai")
    _genai.configure(api_key=cfg.api_key)
    model = _genai.GenerativeModel(
        model_name=cfg.model,
        system_instruction=system_prompt,
    )
    response = model.generate_content(user_prompt)
    return response.text.strip()
```

- [ ] **Step 2: Verify existing transcript tests still pass**

```bash
pytest tests/ -v
```

Expected: `test_config.py` tests still PASS. No regressions.

- [ ] **Step 3: Commit**

```bash
git add src/llm.py
git commit -m "feat(llm): add Gemini provider and call_llm_with_video for video analysis"
```

---

## Task 4: URL utilities

**Files:**
- Create: `src/url_utils.py`
- Create: `tests/test_url_utils.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_url_utils.py`:

```python
import pytest
from src.url_utils import extract_url, extract_context, detect_platform


class TestExtractUrl:
    def test_extracts_https_url(self):
        text = "Check this out https://www.instagram.com/reel/DVHTDqfj9QZ/"
        assert extract_url(text) == "https://www.instagram.com/reel/DVHTDqfj9QZ/"

    def test_returns_none_when_no_url(self):
        assert extract_url("just some text with no link") is None

    def test_extracts_first_url_when_multiple(self):
        text = "https://youtube.com/watch?v=abc and https://instagram.com/reel/xyz"
        assert extract_url(text) == "https://youtube.com/watch?v=abc"

    def test_extracts_url_only_message(self):
        assert extract_url("https://youtu.be/dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"


class TestExtractContext:
    def test_removes_url_and_strips(self):
        text = "Use this framing https://instagram.com/reel/abc for the client deck"
        url = "https://instagram.com/reel/abc"
        assert extract_context(text, url) == "Use this framing  for the client deck".strip()

    def test_returns_empty_string_when_only_url(self):
        url = "https://instagram.com/reel/abc"
        assert extract_context(url, url) == ""

    def test_returns_full_text_when_url_is_none(self):
        text = "just a brain dump"
        assert extract_context(text, None) == "just a brain dump"


class TestDetectPlatform:
    def test_instagram_reel(self):
        assert detect_platform("https://www.instagram.com/reel/DVHTDqfj9QZ/") == "instagram"

    def test_instagram_post(self):
        assert detect_platform("https://www.instagram.com/p/abc123/") == "instagram"

    def test_youtube_full(self):
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"

    def test_youtube_short(self):
        assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"

    def test_youtube_shorts(self):
        assert detect_platform("https://youtube.com/shorts/D3LdwISThoc") == "youtube"

    def test_linkedin(self):
        assert detect_platform("https://www.linkedin.com/posts/chris-tottman_abc") == "linkedin"

    def test_generic_url(self):
        assert detect_platform("https://example.com/article") == "generic"

    def test_none_returns_generic(self):
        assert detect_platform(None) == "generic"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_url_utils.py -v
```

Expected: FAIL — `src/url_utils.py` does not exist.

- [ ] **Step 3: Create `src/url_utils.py`**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_url_utils.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/url_utils.py tests/test_url_utils.py
git commit -m "feat(url-utils): add URL extraction and platform detection"
```

---

## Task 5: Telegram client

**Files:**
- Create: `src/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_telegram.py`:

```python
import json
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_telegram.py -v
```

Expected: FAIL — `src/telegram.py` does not exist.

- [ ] **Step 3: Create `src/telegram.py`**

```python
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
    httpx.post(
        url,
        json={"chat_id": chat_id, "text": text},
        timeout=_TIMEOUT,
    ).raise_for_status()


def get_file_url(token: str, file_id: str) -> str:
    """Resolve a Telegram file_id to a download URL."""
    url = _API_BASE.format(token=token, method="getFile")
    response = httpx.get(url, params={"file_id": file_id}, timeout=_TIMEOUT)
    response.raise_for_status()
    data = response.json()
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
                message_id=msg["message_id"],
                chat_id=chat_id,
                text=msg.get("text"),
                voice_file_id=voice["file_id"] if voice else None,
            )
        )
    return messages
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_telegram.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/telegram.py tests/test_telegram.py
git commit -m "feat(telegram): add polling client, offset persistence, message parsing"
```

---

## Task 6: Fetchers — shared types and YouTube

**Files:**
- Create: `src/fetchers/__init__.py`
- Create: `src/fetchers/youtube.py`
- Create: `tests/test_fetchers.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_fetchers.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from src.fetchers.youtube import fetch_youtube


class TestFetchYoutube:
    def test_returns_transcript_text(self):
        fake_transcript = [
            {"text": "Hello world", "start": 0.0, "duration": 1.0},
            {"text": "this is a test", "start": 1.0, "duration": 1.5},
        ]
        with patch("src.fetchers.youtube.YouTubeTranscriptApi.get_transcript", return_value=fake_transcript):
            result = fetch_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.content == "Hello world this is a test"
        assert result.source_type == "youtube"
        assert result.partial is False
        assert result.failure_reason is None

    def test_handles_no_transcript(self):
        from youtube_transcript_api import TranscriptsDisabled
        with patch(
            "src.fetchers.youtube.YouTubeTranscriptApi.get_transcript",
            side_effect=TranscriptsDisabled("dQw4w9WgXcQ"),
        ):
            result = fetch_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result.partial is True
        assert result.failure_reason is not None
        assert "transcript" in result.failure_reason.lower()

    def test_extracts_video_id_from_youtu_be(self):
        fake_transcript = [{"text": "short link", "start": 0.0, "duration": 1.0}]
        with patch("src.fetchers.youtube.YouTubeTranscriptApi.get_transcript", return_value=fake_transcript) as mock:
            fetch_youtube("https://youtu.be/dQw4w9WgXcQ")
        mock.assert_called_once_with("dQw4w9WgXcQ")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_fetchers.py -v
```

Expected: FAIL — modules don't exist yet.

- [ ] **Step 3: Create `src/fetchers/__init__.py`**

```python
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


def fetch_url(url: str, platform: str, model_config: "ModelConfig") -> FetchResult:
    """Dispatch a URL to the correct fetcher based on platform."""
    if platform == "youtube":
        from src.fetchers.youtube import fetch_youtube
        return fetch_youtube(url)

    if platform == "instagram":
        from src.fetchers.instagram import fetch_instagram
        return fetch_instagram(url, model_config)

    from src.fetchers.generic import fetch_generic
    return fetch_generic(url, platform)
```

- [ ] **Step 4: Create `src/fetchers/youtube.py`**

```python
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
        entries = YouTubeTranscriptApi.get_transcript(video_id)
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_fetchers.py -v
```

Expected: all 3 YouTube tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fetchers/__init__.py src/fetchers/youtube.py tests/test_fetchers.py
git commit -m "feat(fetchers): add FetchResult type, fetch_url dispatcher, YouTube fetcher"
```

---

## Task 7: Generic and LinkedIn fetcher

**Files:**
- Create: `src/fetchers/generic.py`

- [ ] **Step 1: Create `src/fetchers/generic.py`**

```python
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
```

- [ ] **Step 2: Run all tests to confirm no regressions**

```bash
pytest tests/ -v
```

Expected: all existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/fetchers/generic.py
git commit -m "feat(fetchers): add generic trafilatura web scraper"
```

---

## Task 8: Instagram fetcher

**Files:**
- Create: `src/fetchers/instagram.py`

- [ ] **Step 1: Create `src/fetchers/instagram.py`**

```python
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
            except Exception as e:
                # Video downloaded but Gemini analysis failed — fall through to scrape
                pass

    # Fallback: trafilatura caption scrape
    caption_result = fetch_generic(url, platform="instagram")
    if not caption_result.partial:
        # Got caption text — mark as partial since we missed the video audio
        return FetchResult(
            content=caption_result.content,
            source_type="instagram",
            partial=True,
            failure_reason="Video download succeeded but analysis failed, or video unavailable. Caption text only.",
            failure_guidance=None,  # We got something, no action needed
        )

    # Full failure
    return FetchResult(
        content="",
        source_type="instagram",
        partial=True,
        failure_reason="Could not download video or scrape caption.",
        failure_guidance=FAILURE_GUIDANCE["instagram"],
    )
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/fetchers/instagram.py
git commit -m "feat(fetchers): add Instagram fetcher with yt-dlp + Gemini video analysis"
```

---

## Task 9: Voice transcriber

**Files:**
- Create: `src/transcriber.py`

- [ ] **Step 1: Create `src/transcriber.py`**

```python
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
```

- [ ] **Step 2: Run all tests**

```bash
pytest tests/ -v
```

Expected: all existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/transcriber.py
git commit -m "feat(transcriber): add voice note download and Whisper transcription"
```

---

## Task 10: Content classifier

**Files:**
- Create: `src/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_classifier.py`:

```python
import pytest
from src.classifier import _parse_classifier_response, ClassifiedCapture


class TestParseClassifierResponse:
    def test_parses_valid_json(self):
        raw = '''{
            "title": "Jensen Huang on AI Agents",
            "category": "knowledge",
            "tags": ["ai", "strategy"],
            "summary": "Jensen talks about agentic AI.",
            "takeaways": ["Agents will replace SaaS", "Data is the moat"],
            "how_to_use": "Use for client positioning"
        }'''
        result = _parse_classifier_response(raw, source_type="youtube", url="https://youtu.be/abc")
        assert result.title == "Jensen Huang on AI Agents"
        assert result.category == "knowledge"
        assert result.tags == ["ai", "strategy"]
        assert result.summary == "Jensen talks about agentic AI."
        assert result.takeaways == ["Agents will replace SaaS", "Data is the moat"]
        assert result.how_to_use == "Use for client positioning"
        assert result.source_type == "youtube"
        assert result.url == "https://youtu.be/abc"

    def test_strips_markdown_code_fence(self):
        raw = '```json\n{"title": "Test", "category": "inbox", "tags": [], "summary": "s", "takeaways": [], "how_to_use": ""}\n```'
        result = _parse_classifier_response(raw, source_type="text", url=None)
        assert result.title == "Test"

    def test_invalid_category_falls_back_to_inbox(self):
        raw = '{"title": "X", "category": "unknown_category", "tags": [], "summary": "s", "takeaways": [], "how_to_use": ""}'
        result = _parse_classifier_response(raw, source_type="text", url=None)
        assert result.category == "inbox"

    def test_json_parse_error_falls_back_to_inbox(self):
        result = _parse_classifier_response("not json at all", source_type="text", url=None)
        assert result.category == "inbox"
        assert result.title == "Uncategorised capture"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_classifier.py -v
```

Expected: FAIL — `src/classifier.py` does not exist.

- [ ] **Step 3: Create `src/classifier.py`**

```python
"""
Content classifier.
Sends fetched content to Gemini Flash and returns a ClassifiedCapture
with category, title, tags, summary, takeaways, and how_to_use.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import ModelConfig

_VALID_CATEGORIES = {"captures", "ideas", "knowledge", "inbox"}

_SYSTEM_PROMPT = """\
You are a second-brain assistant that classifies and structures captured content.
You always return valid JSON and nothing else — no preamble, no markdown fences.\
"""

_USER_PROMPT_TEMPLATE = """\
Classify and structure the following captured content.

SOURCE TYPE: {source_type}
URL: {url}
USER CONTEXT NOTE: {context_note}

CONTENT:
---
{content}
---

Return a single JSON object with exactly these keys:
- "title": short descriptive title (max 10 words)
- "category": one of "captures" | "ideas" | "knowledge" | "inbox"
  - captures: links, social media content, external resources
  - ideas: app ideas, product concepts, business opportunities
  - knowledge: mindset, frameworks, tactics, learning, strategies
  - inbox: personal brain dumps, mixed content, anything ambiguous
- "tags": list of 2-5 lowercase single-word tags
- "summary": 2-3 sentence explanation of the core idea
- "takeaways": list of 2-5 concrete bullet points
- "how_to_use": the user's context note verbatim if provided, else empty string

Return ONLY the JSON object.\
"""


@dataclass
class ClassifiedCapture:
    title: str
    category: str                     # "captures" | "ideas" | "knowledge" | "inbox"
    tags: list[str]
    summary: str
    takeaways: list[str]
    how_to_use: str
    source_type: str                  # "instagram" | "youtube" | "linkedin" | "text" | "voice" | "generic"
    url: Optional[str]
    raw_content: str


def classify(
    content: str,
    context_note: str,
    source_type: str,
    url: Optional[str],
    model_config: "ModelConfig",
) -> ClassifiedCapture:
    """Send content to Gemini and return a ClassifiedCapture."""
    from src.llm import call_llm

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        source_type=source_type,
        url=url or "none",
        context_note=context_note or "none",
        content=content[:8000],  # Guard against very long content
    )

    raw_response = call_llm(model_config, _SYSTEM_PROMPT, user_prompt)
    return _parse_classifier_response(raw_response, source_type=source_type, url=url, raw_content=content)


def _parse_classifier_response(
    raw: str,
    source_type: str,
    url: Optional[str],
    raw_content: str = "",
) -> ClassifiedCapture:
    """
    Parse the LLM JSON response into a ClassifiedCapture.
    Falls back to an inbox entry if parsing fails.
    """
    # Strip markdown code fences if the model wrapped the JSON
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return _fallback_capture(source_type, url, raw_content)

    category = data.get("category", "inbox")
    if category not in _VALID_CATEGORIES:
        category = "inbox"

    return ClassifiedCapture(
        title=str(data.get("title", "Untitled capture")).strip(),
        category=category,
        tags=[str(t).lower() for t in data.get("tags", [])],
        summary=str(data.get("summary", "")).strip(),
        takeaways=[str(t) for t in data.get("takeaways", [])],
        how_to_use=str(data.get("how_to_use", "")).strip(),
        source_type=source_type,
        url=url,
        raw_content=raw_content,
    )


def _fallback_capture(source_type: str, url: Optional[str], raw_content: str) -> ClassifiedCapture:
    return ClassifiedCapture(
        title="Uncategorised capture",
        category="inbox",
        tags=["needs-review"],
        summary="Could not classify this content automatically.",
        takeaways=[],
        how_to_use="",
        source_type=source_type,
        url=url,
        raw_content=raw_content,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_classifier.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/classifier.py tests/test_classifier.py
git commit -m "feat(classifier): add Gemini content classifier and ClassifiedCapture dataclass"
```

---

## Task 11: Capture note writer

**Files:**
- Create: `src/capture_writer.py`
- Create: `tests/test_capture_writer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_capture_writer.py`:

```python
import pytest
from pathlib import Path
from datetime import date
from src.classifier import ClassifiedCapture
from src.capture_writer import write_capture_note, _build_note_content


class TestBuildNoteContent:
    def _make_capture(self, **overrides) -> ClassifiedCapture:
        defaults = dict(
            title="Test Title",
            category="knowledge",
            tags=["ai", "strategy"],
            summary="This is the summary.",
            takeaways=["Point one", "Point two"],
            how_to_use="Use for client pitches",
            source_type="youtube",
            url="https://youtube.com/watch?v=abc",
            raw_content="raw transcript text here",
        )
        defaults.update(overrides)
        return ClassifiedCapture(**defaults)

    def test_contains_title_in_frontmatter(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert 'title: "Test Title"' in content

    def test_contains_tags(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "#ai" in content or "ai" in content

    def test_contains_summary(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "This is the summary." in content

    def test_contains_takeaways(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "Point one" in content

    def test_contains_how_to_use(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "Use for client pitches" in content

    def test_omits_how_to_use_section_when_empty(self):
        content = _build_note_content(self._make_capture(how_to_use=""), today="2026-06-01")
        assert "How I Want to Use This" not in content

    def test_contains_url(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "https://youtube.com/watch?v=abc" in content


class TestWriteCaptureNote:
    def _make_capture(self, category="knowledge") -> ClassifiedCapture:
        return ClassifiedCapture(
            title="My Test Note",
            category=category,
            tags=["test"],
            summary="Summary here.",
            takeaways=["Point one"],
            how_to_use="",
            source_type="text",
            url=None,
            raw_content="raw text",
        )

    def test_writes_to_correct_folder(self, tmp_path):
        folders = {
            "captures": tmp_path / "Captures",
            "ideas": tmp_path / "Ideas",
            "knowledge": tmp_path / "Knowledge",
            "inbox": tmp_path / "Inbox",
        }
        for f in folders.values():
            f.mkdir()

        path = write_capture_note(self._make_capture(category="knowledge"), folders)
        assert path.parent == folders["knowledge"]

    def test_file_has_md_extension(self, tmp_path):
        folders = {"knowledge": tmp_path / "Knowledge"}
        folders["knowledge"].mkdir()
        path = write_capture_note(self._make_capture(category="knowledge"), folders)
        assert path.suffix == ".md"

    def test_unknown_category_falls_back_to_inbox(self, tmp_path):
        folders = {
            "inbox": tmp_path / "Inbox",
        }
        folders["inbox"].mkdir()
        path = write_capture_note(self._make_capture(category="unknown"), folders)
        assert path.parent == folders["inbox"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_capture_writer.py -v
```

Expected: FAIL — `src/capture_writer.py` does not exist.

- [ ] **Step 3: Create `src/capture_writer.py`**

```python
"""
Capture note writer.
Builds the Markdown note from a ClassifiedCapture and writes it to the
correct vault folder. Handles naming collisions with a counter suffix.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.classifier import ClassifiedCapture


def _safe_filename(title: str) -> str:
    """Convert a title into a safe filesystem name."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    cleaned = re.sub(r"\s+", "-", cleaned).strip("-")
    return cleaned[:80]


def _build_note_content(capture: "ClassifiedCapture", today: str) -> str:
    """Render the Markdown note from a ClassifiedCapture."""
    tags_yaml = ", ".join(capture.tags) if capture.tags else ""
    tags_inline = " ".join(f"#{t}" for t in capture.tags) if capture.tags else ""
    url_line = f"url: {capture.url}" if capture.url else ""
    takeaways = "\n".join(f"- {t}" for t in capture.takeaways) if capture.takeaways else "- None identified"

    how_to_use_section = ""
    if capture.how_to_use:
        how_to_use_section = f"\n## How I Want to Use This\n{capture.how_to_use}\n"

    raw_preview = capture.raw_content[:500] + ("…" if len(capture.raw_content) > 500 else "")
    raw_section = f'\n## Raw Source\n> {raw_preview}\n' if raw_preview else ""

    return f"""\
---
title: "{capture.title}"
date: {today}
type: {capture.category.rstrip('s') if capture.category != 'inbox' else 'brain-dump'}
source: {capture.source_type}
tags: [{tags_yaml}]
{url_line}
---

# {capture.title}

{tags_inline}

## Core Idea
{capture.summary}

## Key Takeaways
{takeaways}
{how_to_use_section}{raw_section}
---
*Captured: {today} · Source: {capture.source_type}*
""".strip() + "\n"


def write_capture_note(
    capture: "ClassifiedCapture",
    capture_folders: dict[str, Path],
) -> Path:
    """
    Write the note to the appropriate vault folder.
    Falls back to 'inbox' if the category folder doesn't exist.
    Returns the path of the written file.
    """
    folder = capture_folders.get(capture.category) or capture_folders.get("inbox")
    if folder is None:
        raise ValueError(
            f"No folder configured for category '{capture.category}' and no 'inbox' fallback."
        )

    today = date.today().isoformat()
    content = _build_note_content(capture, today)
    safe = _safe_filename(capture.title)
    base_name = f"{today}-{safe}.md"
    output_path = folder / base_name

    # Handle naming collisions
    if output_path.exists():
        counter = 2
        while output_path.exists():
            output_path = folder / f"{today}-{safe}-{counter}.md"
            counter += 1

    output_path.write_text(content, encoding="utf-8")
    return output_path
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_capture_writer.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/capture_writer.py tests/test_capture_writer.py
git commit -m "feat(capture-writer): add note builder and vault folder writer"
```

---

## Task 12: Main entry point — capture.py

**Files:**
- Create: `capture.py`

- [ ] **Step 1: Create `capture.py`**

```python
"""
Second Brain — Telegram Capture Pipeline
=========================================
Polls Telegram for new messages, processes each one through the appropriate
fetcher and classifier, writes a note to the Obsidian vault, and sends a
reply confirming what was filed (or what went wrong).

Usage:
    python capture.py          # Process all new messages
    python capture.py --dry-run  # Show what would be processed without doing it
    python capture.py -v         # Verbose output
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from src.config import load_capture_config
from src.url_utils import extract_url, extract_context, detect_platform
from src.telegram import (
    load_offset, save_offset, get_updates,
    send_reply, get_file_url, parse_messages, TelegramMessage,
)
from src.fetchers import fetch_url, FetchResult
from src.classifier import classify, ClassifiedCapture
from src.capture_writer import write_capture_note


def _build_success_reply(capture: ClassifiedCapture, note_path: Path) -> str:
    folder_name = note_path.parent.name
    tags = " ".join(f"#{t}" for t in capture.tags) if capture.tags else ""
    lines = [
        f"✓ Filed to {folder_name}/",
        f"Title: {capture.title}",
    ]
    if tags:
        lines.append(f"Tags: {tags}")
    lines.append(f"Source: {capture.source_type}")
    return "\n".join(lines)


def _build_partial_reply(capture: ClassifiedCapture, note_path: Path, failure_reason: str, guidance: str | None) -> str:
    folder_name = note_path.parent.name
    lines = [
        f"⚠️ Partial capture — filed to {folder_name}/",
        f"Title: {capture.title}",
        f"Issue: {failure_reason}",
    ]
    if guidance:
        lines.append(f"Next step: {guidance}")
    return "\n".join(lines)


def _build_failure_reply(failure_reason: str, guidance: str | None) -> str:
    lines = [
        f"⚠️ Could not capture this content.",
        f"Reason: {failure_reason}",
    ]
    if guidance:
        lines.append(f"Next step: {guidance}")
    else:
        lines.append("Note saved with URL only — nothing was lost.")
    return "\n".join(lines)


def _process_text_message(
    msg: TelegramMessage,
    config,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Handle a plain text or link message. Returns the bot reply text."""
    text = msg.text or ""
    url = extract_url(text)
    context_note = extract_context(text, url)
    platform = detect_platform(url)

    if verbose:
        print(f"    URL: {url or 'none'}, platform: {platform}, context: {context_note!r}")

    if url:
        fetch_result = fetch_url(url, platform, config.capture_model)
        content = fetch_result.content or context_note
        source_type = fetch_result.source_type
    else:
        # Pure text brain dump
        fetch_result = FetchResult(
            content=text, source_type="text",
            partial=False, failure_reason=None, failure_guidance=None
        )
        content = text
        source_type = "text"

    if not content:
        # Complete failure — nothing to classify
        return _build_failure_reply(
            fetch_result.failure_reason or "No content could be retrieved.",
            fetch_result.failure_guidance,
        )

    capture = classify(
        content=content,
        context_note=context_note,
        source_type=source_type,
        url=url,
        model_config=config.capture_model,
    )

    if dry_run:
        return f"[DRY RUN] Would file to {capture.category}/ — {capture.title}"

    note_path = write_capture_note(capture, config.capture_folders)

    if fetch_result.partial:
        return _build_partial_reply(
            capture, note_path,
            fetch_result.failure_reason or "Partial content only",
            fetch_result.failure_guidance,
        )

    return _build_success_reply(capture, note_path)


def _process_voice_message(
    msg: TelegramMessage,
    config,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Handle a voice note. Downloads, transcribes, then classifies."""
    from src.transcriber import download_voice, transcribe_voice
    from src.fetchers import FAILURE_GUIDANCE

    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not openai_api_key:
        return "⚠️ Voice notes require OPENAI_API_KEY to be set in .env. Note not captured."

    ogg_path = None
    try:
        file_url = get_file_url(config.telegram_token, msg.voice_file_id)
        if verbose:
            print(f"    Downloading voice note from Telegram...")

        ogg_path = download_voice(file_url)
        transcript = transcribe_voice(ogg_path, openai_api_key)

        if verbose:
            print(f"    Transcript: {transcript[:80]}...")

        capture = classify(
            content=transcript,
            context_note="",
            source_type="voice",
            url=None,
            model_config=config.capture_model,
        )

        if dry_run:
            return f"[DRY RUN] Would file voice note to {capture.category}/ — {capture.title}"

        note_path = write_capture_note(capture, config.capture_folders)
        return _build_success_reply(capture, note_path)

    except Exception as e:
        # Save the audio file to Untranscribed/ for manual review
        vault_untranscribed = Path(list(config.capture_folders.values())[0]).parent / "Untranscribed"
        vault_untranscribed.mkdir(parents=True, exist_ok=True)
        if ogg_path and ogg_path.exists():
            dest = vault_untranscribed / f"{msg.message_id}.ogg"
            ogg_path.rename(dest)

        return "\n".join([
            "⚠️ Could not process voice note.",
            f"Reason: {e}",
            FAILURE_GUIDANCE["voice"],
        ])
    finally:
        if ogg_path and Path(ogg_path).exists():
            Path(ogg_path).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process Telegram captures into Obsidian notes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing notes or sending replies")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    try:
        config = load_capture_config()
    except (FileNotFoundError, EnvironmentError) as e:
        print(f"Config error: {e}")
        sys.exit(1)

    offset = load_offset(config.offset_file)
    updates = get_updates(config.telegram_token, offset)

    if not updates:
        if args.verbose:
            print("No new messages.")
        return

    print(f"Processing {len(updates)} update(s)...")

    messages = parse_messages(updates, allowed_chat_id=config.telegram_chat_id)
    new_offset = max(u["update_id"] for u in updates)

    for msg in messages:
        msg_type = "voice" if msg.voice_file_id else "text"
        print(f"  [{msg_type}] message_id={msg.message_id} ... ", end="", flush=True)

        try:
            if msg.voice_file_id:
                reply = _process_voice_message(msg, config, args.dry_run, args.verbose)
            else:
                reply = _process_text_message(msg, config, args.dry_run, args.verbose)

            print("OK")
            if args.verbose or args.dry_run:
                print(f"    Reply: {reply}")

            if not args.dry_run:
                send_reply(config.telegram_token, msg.chat_id, reply)

        except Exception as e:
            print(f"ERROR: {e}")
            if not args.dry_run:
                try:
                    send_reply(
                        config.telegram_token, msg.chat_id,
                        f"⚠️ Unexpected error processing your message: {e}\nPlease try again."
                    )
                except Exception:
                    pass  # Don't let a reply failure crash the run

    if not args.dry_run:
        save_offset(config.offset_file, new_offset)

    print(f"Done. Offset saved: {new_offset}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Smoke test with dry-run** *(requires .env filled in with real TELEGRAM_BOT_TOKEN etc.)*

```bash
python capture.py --dry-run -v
```

Expected: either "No new messages." or a dry-run preview with no vault writes.

- [ ] **Step 4: Commit**

```bash
git add capture.py
git commit -m "feat(capture): add main entry point orchestrating full capture pipeline"
```

---

## Task 13: Task Scheduler setup + first live test

**No code files — configuration and manual verification.**

- [ ] **Step 1: Create a Telegram bot**

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`, follow prompts, copy the token
3. Add `TELEGRAM_BOT_TOKEN=<your-token>` to `.env`

- [ ] **Step 2: Get your personal chat ID**

1. Send any message to your new bot
2. Visit in a browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": <NUMBER>}` — that number is your chat ID
4. Add `TELEGRAM_CHAT_ID=<number>` to `.env`

- [ ] **Step 3: Get a Google AI Studio key (free)**

1. Visit https://aistudio.google.com/apikey
2. Click "Create API key"
3. Add `GOOGLE_API_KEY=<key>` to `.env`

- [ ] **Step 4: Verify setup manually**

```bash
.venv\Scripts\activate
python capture.py --dry-run -v
```

Expected: "No new messages." (since you haven't sent anything yet).

- [ ] **Step 5: Send a test message and process it**

Send this message to your bot in Telegram:
```
Great mindset tip — focus on systems not goals https://youtu.be/dQw4w9WgXcQ
```

Then run:
```bash
python capture.py -v
```

Expected output:
```
Processing 1 update(s)...
  [text] message_id=... OK
    Reply: ✓ Filed to Knowledge/
Done. Offset saved: ...
```

Check `C:\Users\user\vault\Knowledge\` for the new note.

- [ ] **Step 6: Set up Task Scheduler**

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task**
3. Name: `Second Brain Capture`
4. Trigger: **Daily** → then edit to repeat
5. Action: **Start a program**
   - Program: `C:\Users\user\OneDrive\Desktop\projects\second-brain v1\.venv\Scripts\python.exe`
   - Arguments: `capture.py`
   - Start in: `C:\Users\user\OneDrive\Desktop\projects\second-brain v1`
6. After creating, **right-click the task → Properties → Triggers → Edit**
7. Check **Repeat task every: 5 minutes** for a duration of **Indefinitely**
8. Click OK

- [ ] **Step 7: Final commit**

```bash
git add docs/superpowers/specs/2026-06-01-telegram-capture-design.md docs/superpowers/plans/2026-06-01-telegram-capture.md
git commit -m "docs: add telegram capture spec and implementation plan"
```

---

## Checklist — spec coverage

| Spec requirement | Task |
|---|---|
| Telegram bot polls for messages | Task 5, 12 |
| Text / brain dump → Gemini Flash | Task 3, 10, 12 |
| YouTube → transcript API → Gemini | Task 6, 10, 12 |
| Instagram → yt-dlp → Gemini video | Task 8, 3 |
| Instagram fallback → trafilatura | Task 7, 8 |
| Voice note → Whisper → Gemini | Task 9, 12 |
| Auto-categorisation (4 folders) | Task 10, 11 |
| Bot reply on every outcome | Task 12 |
| Platform-specific failure guidance | Task 6, 7, 8, `fetchers/__init__.py` |
| Offset persistence (no duplicates) | Task 5 |
| Task Scheduler every 5 min | Task 13 |
| Gemini free tier as default | Task 2, 3 |
| Whisper only for voice (pay-per-use) | Task 9 |
| Vault folders auto-created | Task 2 |
