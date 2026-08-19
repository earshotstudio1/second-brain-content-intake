# Second Brain

A capture and processing pipeline for an Obsidian vault. Things go in from a phone, come out filed correctly, and stay tidy without anyone maintaining them by hand.

## Why it exists

I was capturing plenty and processing almost none of it. Links, half-formed ideas and meeting recordings piled up in an inbox I never opened. The problem was never capture, it was the filing. So the filing became someone else's job.

This runs on a schedule on my own machine and has done since June. It is not a demo.

## What it does

**Capture.** Send anything to a Telegram bot: a URL, a thought, a voice note. It gets fetched, transcribed if needed, classified by an LLM into one of several types (project idea, framework, best practice, reference, tool, personal practice, perspective) and written into the matching vault folder with structured frontmatter.

**Transcripts.** Drop a meeting transcript into a folder. It comes back as a markdown note with a summary, action items with owners, decisions made, blockers and open questions. Processed files are tracked so nothing is done twice.

**Maintenance.** A scheduled sweep over the vault that checks frontmatter consistency, writes a change log, and keeps backups of anything it touches.

**Morning brief.** A daily message with what is actually next, read out of the vault rather than out of a separate to-do app.

## Architecture

- **Classification-first pipeline** — every captured item is typed before it is written, so the destination folder and frontmatter schema follow from the classification rather than from a rule the user has to remember.
- **Pluggable providers** (`src/llm.py`) — OpenAI, Anthropic and Google behind one interface, with the model chosen per workflow in `config.yaml`. Bulk transcript processing runs on a cheap model, and nothing has to change in the code to move it.
- **Idempotent by tracking file** — processed items are appended to a JSONL ledger, so a rerun after a crash picks up cleanly and never duplicates a note.
- **Fetchers and transcribers are separate concerns** (`src/fetchers/`, `src/transcriber.py`) — a captured URL, a YouTube link and a voice note all reduce to text before classification sees them.
- **Vault writes go through one module** (`src/vault.py`, `src/writer.py`) — path resolution, frontmatter and collision handling live in one place, which is what makes the maintenance sweep safe to run.

## Status

Running daily, scheduled via Windows Task Scheduler. Around 3,400 lines of Python with 13 test modules covering classification, capture writing, config, metadata, the maintenance sweep and the URL handling. Windows-first: the scheduling is `.bat` files and Task Scheduler, so running it elsewhere means replacing that layer. Configuration is a single YAML file.

## Setup

Python 3.11. Copy `.env.example` to `.env` and add whichever provider keys you need, copy `config.example.yaml` to `config.yaml` and point `vault_path` at your own vault, then `pip install -r requirements.txt`. Full detail in [docs/](docs/).

MIT licensed.
