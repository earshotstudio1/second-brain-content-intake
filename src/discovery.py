"""
Transcript file discovery.
Finds all files with supported extensions in the input directory.
Sorted by modification time so oldest files are processed first.
"""

from pathlib import Path
from typing import List


def discover_transcripts(input_dir: Path, extensions: List[str]) -> List[Path]:
    """Return transcript files in input_dir, oldest-first."""
    if not input_dir.exists():
        return []

    files: List[Path] = []
    for ext in extensions:
        # Only top-level files — not recursive, keeps it predictable
        files.extend(f for f in input_dir.glob(f"*{ext}") if f.is_file())

    return sorted(files, key=lambda f: f.stat().st_mtime)
