# Telegram Capture Pipeline — Design Spec
**Date:** 2026-06-01  
**Project:** second-brain v1 (extension)  
**Status:** Approved for implementation

---

## Overview

An automated capture pipeline that lets the user send content from their phone (URLs, text brain dumps, voice notes) to a Telegram bot, which processes everything via LLM and files structured notes into the Obsidian vault — with a bot reply confirming exactly what was filed or what failed.

The pipeline extends the existing `second-brain v1` Python project, sharing its config, LLM provider abstraction, vault writer, and tracker infrastructure.

---

## Architecture

```
Phone (Telegram app)
  │  send: URL / text / voice note / forwarded message
  ▼
Telegram Bot API (cloud — just a token, no server)
  │  messages queue in Telegram's update buffer
  ▼
capture.py — Task Scheduler fires every 5 minutes
  │  polls getUpdates, processes new messages, sends reply
  │
  ├─ [text / brain dump]
  │    └─ Gemini Flash: classify + structure → file to vault
  │
  ├─ [URL — Instagram Reel]
  │    ├─ yt-dlp downloads video → Gemini Flash video analysis
  │    ├─ [yt-dlp fails] → trafilatura scrapes caption → Gemini Flash
  │    └─ [both fail] → file URL-only note, bot explains failure
  │
  ├─ [URL — YouTube]
  │    └─ youtube-transcript-api (free) → Gemini Flash summary
  │
  ├─ [URL — LinkedIn / other]
  │    └─ trafilatura scrapes text → Gemini Flash
  │
  └─ [voice note (.ogg)]
       └─ OpenAI Whisper API → Gemini Flash → file to vault
  ▼
Obsidian vault (C:\Users\user\vault)
  ├─ Captures/    ← links and social media content
  ├─ Ideas/       ← app ideas, business concepts
  ├─ Knowledge/   ← mindset, learning, frameworks, tactics
  └─ Inbox/       ← brain dumps / unclassifiable content
  ▼
Bot reply sent to user confirming outcome
```

---

## New vault folders

| Folder | What lands here |
|--------|-----------------|
| `Captures/` | All processed link content (Instagram, YouTube, LinkedIn, other) |
| `Ideas/` | App ideas, product concepts, business opportunities |
| `Knowledge/` | Mindset content, learning, frameworks, tactics, strategies |
| `Inbox/` | *(existing)* Brain dumps, anything unclassifiable |

---

## Note format

Every processed note uses this structure:

```markdown
---
title: "Jensen Huang on AI Agents"
date: 2026-06-01
type: capture          # capture | idea | knowledge | brain-dump
source: instagram      # instagram | youtube | linkedin | telegram | voice | text
tags: [ai, mindset, strategy]
url: https://...       # present for link captures only
---

# Jensen Huang on AI Agents

## Core Idea
2–3 sentence summary of the central message.

## Key Takeaways
- Takeaway one
- Takeaway two

## How I Want to Use This
User's own context note if they sent one alongside the link.
Omitted if not provided.

## Raw Content
> Quoted transcript excerpt or original text (truncated if long)
```

---

## Bot reply format

**On success:**
```
✓ Filed to Knowledge/
Title: Jensen Huang on AI Agents
Tags: #ai #mindset #strategy
Source: instagram
```

**On partial success (caption only, no video):**
```
⚠️ Got the caption but not the video — Instagram blocked the download.
Filed to Captures/ with what was available.
Title: [title from caption]
To get the full video analysis, try a different Reel or paste the caption text directly.
```

**On full failure:**
```
⚠️ Couldn't access this content (Instagram may have updated their block).
Note saved with the URL only — nothing was lost.
Try: paste the caption or description text directly as a message.
```

**Per-platform failure guidance:**

| Platform | Failure message |
|----------|-----------------|
| Instagram | "Instagram blocks automated access. Paste the caption text directly and resend." |
| LinkedIn | "LinkedIn requires login to scrape. Paste the post text directly and resend." |
| YouTube (no transcript) | "This video has no transcript (captions may be disabled). Send a summary in your own words." |
| Voice note | "Could not process voice note. Try re-recording or send as text. Audio saved to Untranscribed/ for manual review." |
| Unknown URL | "Couldn't read content from this URL. Paste the relevant text directly." |

---

## LLM classification prompt

The LLM receives the processed content and returns structured JSON:

```json
{
  "title": "Short descriptive title",
  "category": "captures | ideas | knowledge | inbox",
  "tags": ["tag1", "tag2"],
  "summary": "2-3 sentence core idea",
  "takeaways": ["point one", "point two"],
  "how_to_use": "User's context note or empty string"
}
```

The prompt instructs:
- `captures` — links, social media content, external resources
- `ideas` — app ideas, product concepts, business opportunities, "what if we..."
- `knowledge` — mindset, frameworks, tactics, learning, strategies to apply
- `inbox` — personal brain dumps, mixed content, anything ambiguous

---

## New source modules (`src/`)

| Module | Responsibility |
|--------|----------------|
| `src/telegram.py` | Poll `getUpdates`, parse message types, send replies, store offset |
| `src/fetchers/instagram.py` | yt-dlp download, fall back to trafilatura caption scrape |
| `src/fetchers/youtube.py` | youtube-transcript-api transcript extraction |
| `src/fetchers/generic.py` | trafilatura scrape for LinkedIn and other URLs |
| `src/transcriber.py` | Download Telegram .ogg, convert to mp3, call Whisper API |
| `src/classifier.py` | Send content to Gemini Flash, parse JSON response, return structured data |
| `src/capture_writer.py` | Build note from classified data, write to correct vault folder |

`capture.py` is the entry point — it orchestrates these modules, analogous to `process.py`.

---

## Config additions (`config.yaml`)

```yaml
# Telegram
telegram:
  poll_interval_seconds: 300  # Task Scheduler handles the interval; this is a safety timeout
  offset_file: ".second-brain/telegram_offset.json"

# New vault folders (auto-created on first run)
capture_folders:
  captures: "Captures"
  ideas: "Ideas"
  knowledge: "Knowledge"
  inbox: "Inbox"

# Model for capture processing
models:
  capture_processing:
    provider: google
    model: gemini-2.0-flash
```

---

## Environment variables (`.env`)

```
TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-personal-chat-id
GOOGLE_API_KEY=your-gemini-api-key
```

`OPENAI_API_KEY` already present — used for Whisper voice transcription only.

---

## Reliability & error handling

| Scenario | Behaviour |
|----------|-----------|
| yt-dlp blocked by Instagram | Falls back to caption scrape; bot explains |
| trafilatura scrape fails | Files URL-only note; bot gives platform-specific guidance |
| YouTube has no transcript | Files URL-only note; bot explains |
| Voice note conversion fails | Saves .ogg to `Untranscribed/`; bot notifies |
| Gemini classification fails | Files raw content to `Inbox/` with `needs-review` tag |
| Telegram API unreachable | Exits cleanly; next Task Scheduler tick retries |
| Duplicate message | Telegram message IDs stored in `processed.jsonl`; safe to re-run |

---

## Task Scheduler setup

- **Program:** `.venv\Scripts\python.exe`
- **Arguments:** `capture.py`
- **Start in:** `C:\Users\user\OneDrive\Desktop\projects\second-brain v1`
- **Trigger:** Repeat every 5 minutes, indefinitely
- **Condition:** Run only when on AC power (optional — avoids battery drain on laptop)

---

## New dependencies

```
google-generativeai    # Gemini Flash (free tier)
yt-dlp                 # Instagram / YouTube video download
youtube-transcript-api # YouTube transcript extraction (free, no key)
trafilatura            # Web scraping
pydub                  # Audio conversion (.ogg → .mp3) — requires ffmpeg on system PATH
httpx                  # HTTP client for Telegram API and URL fetching
```

`openai` already installed — used for Whisper only.

---

## Out of scope

- Real-time webhook (requires a server; Task Scheduler polling is sufficient)
- Image analysis from forwarded photos (future extension)
- Cross-note linking / insight generation (future — `insight_generation` model config already stubbed in)
- Group chats or multi-user support (single personal chat only, enforced by `TELEGRAM_CHAT_ID`)
