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
