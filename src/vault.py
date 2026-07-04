"""Helpers for reading and writing Obsidian vault notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.metadata import build_metadata, render_frontmatter


PROFILE_TEMPLATES: dict[str, str] = {
    "Profile/Long-Term Goals.md": """\
# Long-Term Goals

## Who I Am Becoming
- 

## Outcomes I Care About
- 

## Why This Matters
- 
""",
    "Profile/Current Priorities.md": """\
# Current Priorities

## This Season's Focus
- 

## Active Trade-Offs
- 

## What To Ignore For Now
- 
""",
    "Profile/Skills I Want To Build.md": """\
# Skills I Want To Build

## Skills
- 

## Evidence I Am Improving
- 

## Useful Resources
- 
""",
    "Profile/Personal Context.md": """\
# Personal Context

## Work
- 

## Life
- 

## Constraints And Preferences
- 
""",
    "Profile/Principles.md": """\
# Principles

## How I Want To Operate
- 

## Standards
- 

## Reminders
- 
""",
    "Profile/Current Projects.md": """\
# Current Projects

## Active Projects
- 

## Paused Projects
- 

## Possible Next Projects
- 
""",
}


GROWTH_TEMPLATES: dict[str, str] = {
    "Growth/Skill Gaps.md": """\
# Skill Gaps

## Current Gaps
- 

## Evidence
- 

## Next Review
- 
""",
    "Growth/Learning Plan.md": """\
# Learning Plan

## Focus Areas
- 

## Resources
- 

## Practice Blocks
- 
""",
    "Growth/Experiments.md": """\
# Experiments

## Active Experiments
- [ ] 

## Completed Experiments
- 

## Lessons
- 
""",
}


@dataclass(frozen=True)
class VaultNote:
    """A markdown note discovered in the vault."""

    path: Path
    relative_path: str
    modified_at: datetime
    content: str | None = None


def ensure_profile_templates(vault_path: Path) -> list[Path]:
    """Create missing Profile notes and return the paths that were created."""
    created: list[Path] = []
    for relative_path, content in PROFILE_TEMPLATES.items():
        path = vault_path / relative_path
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _render_template_note(
                content=content,
                note_type="profile",
                source="manual",
                workflow="profile_template",
            ),
            encoding="utf-8",
        )
        created.append(path)
    return created


def ensure_growth_templates(vault_path: Path) -> list[Path]:
    """Create missing Growth foundation notes and return paths created."""
    created: list[Path] = []
    for relative_path, content in GROWTH_TEMPLATES.items():
        path = vault_path / relative_path
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _render_template_note(
                content=content,
                note_type="growth-note",
                source="manual",
                workflow="growth_coach",
            ),
            encoding="utf-8",
        )
        created.append(path)
    (vault_path / "Growth" / "Growth Reviews").mkdir(parents=True, exist_ok=True)
    return created


def list_recent_markdown_files(
    vault_path: Path,
    folder_names: list[str],
    days: int = 7,
    now: datetime | None = None,
) -> list[VaultNote]:
    """List markdown files in selected folders modified within the last N days."""
    if days < 1:
        raise ValueError("days must be at least 1")

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    cutoff = current_time - timedelta(days=days)

    notes: list[VaultNote] = []
    for folder_name in folder_names:
        folder = vault_path / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.md"):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < cutoff:
                continue
            notes.append(
                VaultNote(
                    path=path,
                    relative_path=path.relative_to(vault_path).as_posix(),
                    modified_at=modified_at,
                )
            )

    return sorted(notes, key=lambda note: (note.modified_at, note.relative_path), reverse=True)


def read_notes(notes: list[VaultNote]) -> list[VaultNote]:
    """Return copies of notes with markdown content loaded."""
    return [
        VaultNote(
            path=note.path,
            relative_path=note.relative_path,
            modified_at=note.modified_at,
            content=note.path.read_text(encoding="utf-8"),
        )
        for note in notes
    ]


def read_profile_notes(vault_path: Path) -> dict[str, str]:
    """Read the canonical Profile notes, creating missing templates first."""
    ensure_profile_templates(vault_path)
    profile: dict[str, str] = {}
    for relative_path in PROFILE_TEMPLATES:
        path = vault_path / relative_path
        profile[relative_path] = path.read_text(encoding="utf-8")
    return profile


def read_growth_notes(vault_path: Path) -> dict[str, str]:
    """Read the canonical Growth foundation notes, creating missing templates first."""
    ensure_growth_templates(vault_path)
    growth: dict[str, str] = {}
    for relative_path in GROWTH_TEMPLATES:
        path = vault_path / relative_path
        growth[relative_path] = path.read_text(encoding="utf-8")
    return growth


def find_latest_markdown_file(vault_path: Path, folder_name: str) -> VaultNote | None:
    """Find the newest markdown file in a vault folder by modified time."""
    folder = vault_path / folder_name
    if not folder.exists():
        return None
    candidates = sorted(
        folder.rglob("*.md"),
        key=lambda path: (path.stat().st_mtime, path.relative_to(vault_path).as_posix()),
        reverse=True,
    )
    if not candidates:
        return None
    path = candidates[0]
    return VaultNote(
        path=path,
        relative_path=path.relative_to(vault_path).as_posix(),
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
        content=path.read_text(encoding="utf-8"),
    )


def _render_template_note(content: str, note_type: str, source: str, workflow: str) -> str:
    title = content.splitlines()[0].removeprefix("# ").strip()
    today = date.today().isoformat()
    metadata = build_metadata(
        title=title,
        note_type=note_type,
        source=source,
        tags=[],
        workflow=workflow,
        today=today,
    )
    return render_frontmatter(metadata, content)


def write_note_safely(
    vault_path: Path,
    relative_path: str,
    content: str,
    overwrite: bool = True,
) -> Path:
    """Write a note inside the vault, refusing path traversal."""
    vault_root = vault_path.resolve()
    output_path = (vault_path / relative_path).resolve()
    if vault_root != output_path and vault_root not in output_path.parents:
        raise ValueError(f"Refusing to write outside vault: {relative_path}")
    if output_path.exists() and not overwrite:
        raise FileExistsError(f"Note already exists: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return output_path
