"""
Note writer.
Derives an output filename from the note's frontmatter title,
handles naming collisions, and writes the file to the output directory.
"""

import re
from datetime import date
from pathlib import Path

from .config import Config


def _extract_title(note_content: str, fallback: str) -> str:
    """Pull the title from YAML frontmatter."""
    match = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', note_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def _safe_filename(title: str) -> str:
    """Convert a title to a safe filesystem name."""
    # Remove characters that are illegal in Windows/Mac filenames
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    # Collapse whitespace to hyphens
    cleaned = re.sub(r'\s+', "-", cleaned).strip("-")
    # Cap at 80 characters to keep paths sane
    return cleaned[:80]


def write_note(note_content: str, source_file: Path, config: Config) -> Path:
    """Write the note and return its path. Handles naming collisions."""
    title = _extract_title(note_content, fallback=source_file.stem)
    safe = _safe_filename(title)
    today = date.today().isoformat()

    base_name = f"{today}-{safe}.md"
    output_path = config.output_dir / base_name

    # If a file with this name already exists, append a counter
    if output_path.exists():
        counter = 2
        while output_path.exists():
            output_path = config.output_dir / f"{today}-{safe}-{counter}.md"
            counter += 1

    output_path.write_text(note_content, encoding="utf-8")
    return output_path
