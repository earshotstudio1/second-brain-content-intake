"""
Processed-file tracker.
Uses a JSONL file to record which transcripts have been processed and
what their content hash was at the time. If a file is modified after
processing, its hash changes and it will be picked up again.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class Tracker:
    def __init__(self, tracking_file: Path) -> None:
        self._file = tracking_file
        # keyed by absolute file path string
        self._records: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        self._records[entry["file"]] = entry
                    except (json.JSONDecodeError, KeyError):
                        pass  # Corrupt line — skip, don't crash

    def _hash(self, path: Path) -> str:
        """SHA-256 of file contents, truncated to 16 hex chars."""
        h = hashlib.sha256(path.read_bytes())
        return h.hexdigest()[:16]

    def is_processed(self, path: Path) -> bool:
        key = str(path.resolve())
        if key not in self._records:
            return False
        stored_hash = self._records[key].get("hash")
        return stored_hash == self._hash(path)

    def mark_processed(self, source: Path, output: Path) -> None:
        entry = {
            "file": str(source.resolve()),
            "name": source.name,
            "hash": self._hash(source),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "output": str(output.resolve()),
        }
        self._records[entry["file"]] = entry
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
