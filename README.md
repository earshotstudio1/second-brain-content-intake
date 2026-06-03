# Second Brain — Transcript Processor

Turns raw meeting transcripts in your Obsidian vault into structured, operationally useful markdown notes.

Supports multiple LLM providers — use OpenAI for cheap bulk transcript processing and reserve Claude for higher-value work later.

---

## What it does

1. Reads transcript files from `Transcripts/` in your vault
2. Sends each one to the configured LLM
3. Writes a clean markdown note to `Meetings/` in your vault
4. Tracks processed files so nothing is duplicated

Each output note contains:

- **Summary** — 3–5 sentence overview of the meeting
- **Action Items** — checkboxes with owner names where identifiable
- **Decisions Made** — concrete agreements reached
- **Blockers / Risks** — anything that could slow progress
- **Follow-ups / Open Questions** — things that need chasing

---

## Vault structure

```
vault/
├── Transcripts/          ← Drop transcript files here
├── Meetings/             ← Processed notes appear here (auto-created)
└── .second-brain/
    └── processed.jsonl   ← Tracks which files have been processed
```

---

## Setup (one time)

### 1. Open this folder in VS Code

```
C:\Users\user\OneDrive\Desktop\projects\second-brain
```

### 2. Create a virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your API keys

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` and fill in the key(s) you need:

```
ANTHROPIC_API_KEY=your-anthropic-key-here
OPENAI_API_KEY=your-openai-key-here
```

You only need the key for the provider(s) you actually use. The system will
tell you clearly at startup if a required key is missing.

- Anthropic API: https://console.anthropic.com
- OpenAI API: https://platform.openai.com/api-keys

### 5. Check config.yaml

The vault path and model config are already set. See the configuration
section below if you want to change provider or model.

---

## Running it

```bash
# Make sure the venv is active first:
.venv\Scripts\activate

# Process all new transcripts
python process.py

# See what would be processed without actually doing it
python process.py --dry-run

# Reprocess files that have already been processed
python process.py --force

# Process a single specific file
python process.py --file "C:/Users/user/vault/Transcripts/my-meeting.txt"

# Verbose output (shows skipped files too)
python process.py -v
```

---

## Provider and model configuration

Everything is in the `models:` section of `config.yaml`. Each entry is a
workflow. Right now there is one: `transcript_processing`.

```yaml
models:
  transcript_processing:
    provider: openai        # anthropic | openai
    model: gpt-4o-mini
```

### Switching provider

Change `provider:` and `model:` and restart. No code changes needed.

```yaml
# Use OpenAI (cheap, good for bulk transcript processing)
models:
  transcript_processing:
    provider: openai
    model: gpt-4o-mini

# Or switch to Claude for higher quality
models:
  transcript_processing:
    provider: anthropic
    model: claude-sonnet-4-6
```

### Recommended practical setup

| Workflow | Provider | Model | Why |
|---|---|---|---|
| Transcript processing | OpenAI | `gpt-4o-mini` | Cheap, fast, handles bulk well |
| Insight generation (future) | Anthropic | `claude-sonnet-4-6` | Better reasoning, worth the cost |

This is why both keys exist — transcript processing burns through volume,
so OpenAI is the right default. When you later add workflows that require
deeper reasoning (weekly reviews, cross-meeting insights), you can assign
those to Claude without touching the transcript pipeline.

### Available models

**OpenAI:**
- `gpt-4o-mini` — cheap and fast, good default for transcripts
- `gpt-4o` — higher quality, higher cost

**Anthropic:**
- `claude-haiku-4-5-20251001` — fastest and cheapest Claude option
- `claude-sonnet-4-6` — best balance
- `claude-opus-4-6` — highest quality

### Adding a second workflow later

When you add `insights.py` or another processing script, add its model
config to `config.yaml`:

```yaml
models:
  transcript_processing:
    provider: openai
    model: gpt-4o-mini

  insight_generation:
    provider: anthropic
    model: claude-sonnet-4-6
```

Then in your new script, access it via `config.models["insight_generation"]`.

---

## Testing with your existing transcripts

```bash
# Dry run first — see what will be processed
python process.py --dry-run

# Process one file to verify the output looks right
python process.py --file "C:/Users/user/vault/Transcripts/MDP meeting 1_original.txt"
```

The output note will appear in `Meetings/` named like:
```
2026-04-07-MDP-Meeting-1.md
```

Open it in Obsidian to check it looks right, then process everything:

```bash
python process.py
```

---

## Supported file formats

| Extension | Notes |
|-----------|-------|
| `.txt` | UTF-16 (your current format) and UTF-8 both supported |
| `.md` | Plain markdown transcripts |
| `.vtt` | WebVTT subtitles |
| `.srt` | SRT subtitles |

---

## Configuration reference

| Key | Description |
|-----|-------------|
| `vault_path` | Absolute path to your Obsidian vault |
| `input_folder` | Where you drop transcript files (relative to vault) |
| `output_folder` | Where processed notes are written (relative to vault) |
| `tracking_file` | Processed-file log (relative to vault) |
| `supported_extensions` | File types to scan for |
| `models.transcript_processing.provider` | `anthropic` or `openai` |
| `models.transcript_processing.model` | Model name for that provider |

---

## How processed-file tracking works

After a file is processed, its SHA-256 hash is stored in `.second-brain/processed.jsonl`.
If you modify a transcript after processing, the hash changes and it will
be re-processed automatically on the next run.
Use `--force` to re-process files regardless.

---

## Running automatically (optional)

### Windows Task Scheduler

1. Open Task Scheduler → Create Basic Task
2. Trigger: Daily or On Logon
3. Action: Start a program
   - Program: `C:\Users\user\OneDrive\Desktop\projects\second-brain\.venv\Scripts\python.exe`
   - Arguments: `process.py`
   - Start in: `C:\Users\user\OneDrive\Desktop\projects\second-brain`

---

## Telegram Capture Pipeline

Captures content you send from your phone (links, brain dumps, voice notes) and files them into your vault automatically.

### One-time setup

#### 1. Create a Telegram bot

1. Open Telegram → search **@BotFather** → send `/newbot`
2. Follow the prompts and copy your bot token
3. Add to `.env`: `TELEGRAM_BOT_TOKEN=<your-token>`

#### 2. Get your personal chat ID

1. Send any message to your new bot in Telegram
2. Visit in a browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": <NUMBER>}` — that number is your chat ID
4. Add to `.env`: `TELEGRAM_CHAT_ID=<number>`

#### 3. Get a Google AI Studio key (free)

1. Visit https://aistudio.google.com/apikey → Create API key
2. Add to `.env`: `GOOGLE_API_KEY=<key>`

#### 4. Install ffmpeg (required for voice notes)

Download from https://ffmpeg.org/download.html and ensure `ffmpeg` is on your PATH.
Test: `ffmpeg -version` should print a version number.

#### 5. Verify setup

```bash
.venv\Scripts\activate
python capture.py --dry-run -v
```

Expected: "No new messages." (nothing sent yet).

#### 6. Set up Task Scheduler (runs every 5 minutes)

1. Open **Task Scheduler** (search Start menu)
2. Click **Create Basic Task** → Name: `Second Brain Capture`
3. Trigger: **Daily** → finish wizard → then right-click task → Properties
4. **Triggers** tab → Edit → check **Repeat task every: 5 minutes** for **Indefinitely** → OK
5. **Actions** tab → Edit:
   - Program: `C:\Users\user\OneDrive\Desktop\projects\second-brain v1\.venv\Scripts\python.exe`
   - Arguments: `capture.py`
   - Start in: `C:\Users\user\OneDrive\Desktop\projects\second-brain v1`
6. **Conditions** tab → optionally check "Start only if on AC power"

### Running manually

```bash
.venv\Scripts\activate

# Process new messages now
python capture.py

# Preview without writing to vault or sending replies
python capture.py --dry-run

# Verbose output
python capture.py -v
```

### What gets captured

| You send | How it's processed | Filed to |
|---|---|---|
| Text / brain dump | Gemini Flash classifies | `Inbox/`, `Knowledge/`, `Ideas/`, or `Captures/` |
| Instagram Reel URL | yt-dlp downloads → Gemini video analysis | `Captures/` |
| YouTube URL | Free transcript API → Gemini summary | `Captures/` or `Knowledge/` |
| LinkedIn / other URL | trafilatura scrape → Gemini | `Captures/` |
| Voice note | Whisper transcribes → Gemini classifies | varies |

### Bot replies

After processing each message you'll receive a Telegram reply within ~5 minutes:

**Success:**
```
✓ Filed to Knowledge/
Title: Jensen Huang on AI Agents
Tags: #ai #strategy #mindset
Source: youtube
```

**Partial (e.g. Instagram caption only):**
```
⚠️ Partial capture — filed to Captures/
Title: ...
Issue: Video download failed. Caption text only.
```

**Failure:**
```
⚠️ Could not capture this content.
Reason: Instagram blocked the download.
Next step: Paste the caption text directly and resend.
```

### Vault folders created

| Folder | Contents |
|---|---|
| `Captures/` | Links and social media content |
| `Ideas/` | App ideas, product concepts, business opportunities |
| `Knowledge/` | Mindset, frameworks, tactics, learning |
| `Inbox/` | Brain dumps and anything unclassifiable |

---

## Future ideas

1. **Daily brief** — aggregates open action items from recent meetings into one note each morning
2. **Task aggregation** — scrapes all `- [ ]` lines across `Meetings/` into a single pending tasks note
3. **Weekly review** — digest of all meetings from the past 7 days (good candidate for Claude)
4. **Note linking** — auto-add `[[wikilinks]]` when two notes mention the same person or project

---

## Troubleshooting

**`OPENAI_API_KEY is not set`**
→ Add it to your `.env` file. Only the key for the provider you're actively using is required.

**`Unknown provider 'x'`**
→ Check `models.transcript_processing.provider` in `config.yaml`. Valid values: `anthropic`, `openai`.

**`Vault path does not exist`**
→ Check `vault_path` in `config.yaml` matches where your vault actually lives.

**`No transcript files found`**
→ Transcript files must be directly inside `Transcripts/` (not in subfolders) with a supported extension.

**Output note looks garbled**
→ The transcript may be in an unusual encoding. Open it in VS Code and check the encoding in the status bar (bottom right).

**Want to reset and reprocess everything**
→ Delete `.second-brain/processed.jsonl` and run `python process.py`.
