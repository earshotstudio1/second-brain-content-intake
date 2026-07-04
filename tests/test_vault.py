from datetime import datetime, timedelta, timezone
import os

import pytest

from src.vault import (
    GROWTH_TEMPLATES,
    PROFILE_TEMPLATES,
    ensure_profile_templates,
    ensure_growth_templates,
    find_latest_markdown_file,
    list_recent_markdown_files,
    read_growth_notes,
    read_profile_notes,
    write_note_safely,
)


def test_ensure_profile_templates_creates_missing_files(tmp_path):
    created = ensure_profile_templates(tmp_path)

    assert len(created) == len(PROFILE_TEMPLATES)
    for relative_path in PROFILE_TEMPLATES:
        assert (tmp_path / relative_path).exists()


def test_ensure_profile_templates_preserves_existing_file(tmp_path):
    existing = tmp_path / "Profile" / "Long-Term Goals.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("# My real goals\n", encoding="utf-8")

    ensure_profile_templates(tmp_path)

    assert existing.read_text(encoding="utf-8") == "# My real goals\n"


def test_read_profile_notes_returns_all_templates(tmp_path):
    notes = read_profile_notes(tmp_path)

    assert set(notes) == set(PROFILE_TEMPLATES)
    assert "# Current Priorities" in notes["Profile/Current Priorities.md"]


def test_ensure_growth_templates_creates_foundation_notes(tmp_path):
    created = ensure_growth_templates(tmp_path)

    assert len(created) == len(GROWTH_TEMPLATES)
    assert (tmp_path / "Growth" / "Growth Reviews").exists()
    for relative_path in GROWTH_TEMPLATES:
        assert (tmp_path / relative_path).exists()


def test_read_growth_notes_returns_all_templates(tmp_path):
    notes = read_growth_notes(tmp_path)

    assert set(notes) == set(GROWTH_TEMPLATES)
    assert "# Experiments" in notes["Growth/Experiments.md"]


def test_list_recent_markdown_files_filters_by_folder_and_mtime(tmp_path):
    now = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    recent = tmp_path / "Captures" / "recent.md"
    old = tmp_path / "Captures" / "old.md"
    ignored = tmp_path / "Archive" / "ignored.md"
    for path in [recent, old, ignored]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")

    old_time = (now - timedelta(days=8)).timestamp()
    recent_time = (now - timedelta(days=2)).timestamp()
    os.utime(old, (old_time, old_time))
    os.utime(recent, (recent_time, recent_time))
    os.utime(ignored, (recent_time, recent_time))

    notes = list_recent_markdown_files(tmp_path, ["Captures"], days=7, now=now)

    assert [note.relative_path for note in notes] == ["Captures/recent.md"]


def test_write_note_safely_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="outside vault"):
        write_note_safely(tmp_path, "../outside.md", "nope")


def test_write_note_safely_can_refuse_overwrite(tmp_path):
    write_note_safely(tmp_path, "Reviews/Weekly/2026-W24.md", "first")

    with pytest.raises(FileExistsError):
        write_note_safely(
            tmp_path,
            "Reviews/Weekly/2026-W24.md",
            "second",
            overwrite=False,
        )


def test_find_latest_markdown_file_returns_newest(tmp_path):
    older = tmp_path / "Reviews" / "Weekly" / "2026-W23.md"
    newer = tmp_path / "Reviews" / "Weekly" / "2026-W24.md"
    older.parent.mkdir(parents=True)
    older.write_text("# Old", encoding="utf-8")
    newer.write_text("# New", encoding="utf-8")
    old_time = datetime(2026, 6, 7, tzinfo=timezone.utc).timestamp()
    new_time = datetime(2026, 6, 14, tzinfo=timezone.utc).timestamp()
    os.utime(older, (old_time, old_time))
    os.utime(newer, (new_time, new_time))

    note = find_latest_markdown_file(tmp_path, "Reviews/Weekly")

    assert note is not None
    assert note.relative_path == "Reviews/Weekly/2026-W24.md"
    assert note.content == "# New"
