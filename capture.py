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
        lines.append("Nothing was captured — no fallback was available.")
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
            suffix = "..." if len(transcript) > 80 else ""
            print(f"    Transcript: {transcript[:80]}{suffix}")

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
    else:
        print(f"Done. (dry run — offset not saved, would have been: {new_offset})")


if __name__ == "__main__":
    main()
