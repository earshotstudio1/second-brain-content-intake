"""Generate a weekly review note from recent vault activity."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import ModelConfig, load_workflow_config
from src.metadata import build_metadata, parse_frontmatter, render_frontmatter
from src.vault import (
    VaultNote,
    ensure_profile_templates,
    list_recent_markdown_files,
    read_notes,
    read_profile_notes,
    write_note_safely,
)


REVIEW_SOURCE_FOLDERS = ["Captures", "Ideas", "Personal", "Projects", "Knowledge", "Perspective", "Meetings", "Inbox"]
MAX_NOTE_CHARS = 3500

SYSTEM_PROMPT = """\
You are a grounded second-brain weekly review assistant.

Rules:
- Use only the supplied vault context.
- Be specific and practical. Avoid vague coaching language.
- Preserve the user's own language where it reveals priorities or patterns.
- If there is not enough evidence for a section, write "- None identified".
- Return only the markdown review.
"""


@dataclass(frozen=True)
class WeeklyReviewResult:
    output_path: Path
    content: str
    recent_note_count: int
    created_profile_templates: list[Path]


def weekly_review_relative_path(target_date: date) -> str:
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"Reviews/Weekly/{iso_year}-W{iso_week:02d}.md"


def _format_profile_context(profile_notes: dict[str, str]) -> str:
    blocks = []
    for relative_path, content in profile_notes.items():
        blocks.append(f"## {relative_path}\n{content.strip() or '- Empty'}")
    return "\n\n".join(blocks)


def _format_recent_notes(notes: list[VaultNote]) -> str:
    if not notes:
        return "- No recent notes found."

    blocks = []
    for note in notes:
        content = (note.content or "").strip()
        if len(content) > MAX_NOTE_CHARS:
            content = content[:MAX_NOTE_CHARS].rstrip() + "\n[truncated]"
        blocks.append(
            "\n".join(
                [
                    f"## {note.relative_path}",
                    f"Modified: {note.modified_at.date().isoformat()}",
                    content or "- Empty",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_weekly_review_prompt(
    profile_notes: dict[str, str],
    recent_notes: list[VaultNote],
    target_date: date,
) -> str:
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"""\
Create the weekly review for ISO week {iso_year}-W{iso_week:02d}.

PROFILE CONTEXT:
---
{_format_profile_context(profile_notes)}
---

RECENT VAULT NOTES:
---
{_format_recent_notes(recent_notes)}
---

Return the note using exactly this structure:

# Weekly Review - {iso_year}-W{iso_week:02d}

## What Happened

## Important Captures

## Recurring Themes

## Open Loops

## Progress Against Goals

## Useful Signals
Identify opportunity signals in recent meeting notes, possible project ideas in captures or Projects/Ideas, personal practice ideas worth trying, knowledge/frameworks worth testing, and perspective notes that may affect growth or decision-making.

## Suggested Focus For Next Week
"""


def run_weekly_review(
    vault_path: Path,
    model_config: ModelConfig,
    dry_run: bool = False,
    target_date: date | None = None,
    now: datetime | None = None,
) -> WeeklyReviewResult:
    target = target_date or date.today()
    created_templates = ensure_profile_templates(vault_path)
    profile_notes = read_profile_notes(vault_path)
    recent_notes = read_notes(
        list_recent_markdown_files(
            vault_path=vault_path,
            folder_names=REVIEW_SOURCE_FOLDERS,
            days=7,
            now=now or datetime.now(timezone.utc),
        )
    )
    prompt = build_weekly_review_prompt(profile_notes, recent_notes, target)
    relative_path = weekly_review_relative_path(target)
    output_path = vault_path / relative_path

    if dry_run:
        return WeeklyReviewResult(
            output_path=output_path,
            content=prompt,
            recent_note_count=len(recent_notes),
            created_profile_templates=created_templates,
        )

    from src.llm import call_llm

    content = call_llm(model_config, SYSTEM_PROMPT, prompt)
    parsed = parse_frontmatter(content)
    if not parsed.has_frontmatter:
        iso_year, iso_week, _ = target.isocalendar()
        metadata = build_metadata(
            title=f"Weekly Review - {iso_year}-W{iso_week:02d}",
            note_type="review",
            source="workflow",
            tags=["weekly-review"],
            workflow="weekly_review",
            today=target.isoformat(),
            domain="growth",
            stage="active",
            model=model_config.model,
        )
        content = render_frontmatter(metadata, parsed.body)
    output_path = write_note_safely(vault_path, relative_path, content, overwrite=True)
    return WeeklyReviewResult(
        output_path=output_path,
        content=content,
        recent_note_count=len(recent_notes),
        created_profile_templates=created_templates,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Obsidian weekly review")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without calling the LLM")
    args = parser.parse_args()

    config = load_workflow_config("weekly_review")
    result = run_weekly_review(
        vault_path=config.vault_path,
        model_config=config.model,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(result.content)
        print(f"\n[DRY RUN] Would write: {result.output_path}")
    else:
        print(f"Wrote weekly review: {result.output_path}")
    if result.created_profile_templates:
        print(f"Created {len(result.created_profile_templates)} missing Profile template(s).")
    print(f"Reviewed {result.recent_note_count} recent note(s).")


if __name__ == "__main__":
    main()
