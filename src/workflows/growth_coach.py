"""Generate grounded growth coaching from the Obsidian vault."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from src.config import ModelConfig, load_workflow_config
from src.metadata import build_metadata, parse_frontmatter, render_frontmatter
from src.vault import (
    VaultNote,
    ensure_growth_templates,
    ensure_profile_templates,
    find_latest_markdown_file,
    list_recent_markdown_files,
    read_growth_notes,
    read_notes,
    read_profile_notes,
    write_note_safely,
)


GROWTH_SOURCE_FOLDERS = ["Captures", "Ideas", "Personal", "Projects", "Knowledge", "Perspective", "Meetings", "Inbox"]
MAX_NOTE_CHARS = 3000

SYSTEM_PROMPT = """\
You are a grounded growth coach for a personal Obsidian second brain.

Rules:
- Use only the supplied vault context.
- Avoid vague life-coach language.
- Anchor every recommendation in evidence from notes, profile, reviews, or captures.
- Prefer small concrete experiments over broad intentions.
- If there is not enough evidence for a section, write "- None identified".
- Return only the markdown review.
"""


@dataclass(frozen=True)
class GrowthCoachResult:
    output_path: Path
    content: str
    recent_note_count: int
    latest_weekly_review_path: Path | None
    created_profile_templates: list[Path]
    created_growth_templates: list[Path]


def growth_review_relative_path(target_date: date) -> str:
    iso_year, iso_week, _ = target_date.isocalendar()
    return f"Growth/Growth Reviews/{iso_year}-W{iso_week:02d}.md"


def _format_note_map(title: str, notes: dict[str, str]) -> str:
    blocks = [f"# {title}"]
    for relative_path, content in notes.items():
        blocks.append(f"## {relative_path}\n{content.strip() or '- Empty'}")
    return "\n\n".join(blocks)


def _format_vault_notes(notes: list[VaultNote]) -> str:
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


def build_growth_coach_prompt(
    profile_notes: dict[str, str],
    growth_notes: dict[str, str],
    latest_weekly_review: VaultNote | None,
    recent_notes: list[VaultNote],
    target_date: date,
) -> str:
    iso_year, iso_week, _ = target_date.isocalendar()
    weekly_review_block = "- No weekly review found yet."
    if latest_weekly_review:
        weekly_review_block = "\n".join(
            [
                f"## {latest_weekly_review.relative_path}",
                latest_weekly_review.content or "- Empty",
            ]
        )

    return f"""\
Create the growth review for ISO week {iso_year}-W{iso_week:02d}.

PROFILE CONTEXT:
---
{_format_note_map("Profile", profile_notes)}
---

GROWTH FOUNDATION NOTES:
---
{_format_note_map("Growth", growth_notes)}
---

LATEST WEEKLY REVIEW:
---
{weekly_review_block}
---

RECENT VAULT NOTES:
---
{_format_vault_notes(recent_notes)}
---

Return the note using exactly this structure:

# Growth Review - {iso_year}-W{iso_week:02d}

## Signals This Week
Distinguish personal practice, projects, knowledge, and perspective signals. Explicitly look for opportunity signals in recent meeting notes and possible project ideas in captures.

## Likely Growth Areas

## Knowledge Gaps

## Recommended Learning

## This Week's Experiments
"""


def run_growth_coach(
    vault_path: Path,
    model_config: ModelConfig,
    dry_run: bool = False,
    target_date: date | None = None,
    now: datetime | None = None,
) -> GrowthCoachResult:
    target = target_date or date.today()
    created_profile_templates = ensure_profile_templates(vault_path)
    created_growth_templates = ensure_growth_templates(vault_path)
    profile_notes = read_profile_notes(vault_path)
    growth_notes = read_growth_notes(vault_path)
    latest_weekly_review = find_latest_markdown_file(vault_path, "Reviews/Weekly")
    recent_notes = read_notes(
        list_recent_markdown_files(
            vault_path=vault_path,
            folder_names=GROWTH_SOURCE_FOLDERS,
            days=7,
            now=now or datetime.now(timezone.utc),
        )
    )
    prompt = build_growth_coach_prompt(
        profile_notes=profile_notes,
        growth_notes=growth_notes,
        latest_weekly_review=latest_weekly_review,
        recent_notes=recent_notes,
        target_date=target,
    )
    relative_path = growth_review_relative_path(target)
    output_path = vault_path / relative_path

    if dry_run:
        return GrowthCoachResult(
            output_path=output_path,
            content=prompt,
            recent_note_count=len(recent_notes),
            latest_weekly_review_path=latest_weekly_review.path if latest_weekly_review else None,
            created_profile_templates=created_profile_templates,
            created_growth_templates=created_growth_templates,
        )

    from src.llm import call_llm

    content = call_llm(model_config, SYSTEM_PROMPT, prompt)
    parsed = parse_frontmatter(content)
    if not parsed.has_frontmatter:
        iso_year, iso_week, _ = target.isocalendar()
        metadata = build_metadata(
            title=f"Growth Review - {iso_year}-W{iso_week:02d}",
            note_type="growth-review",
            source="workflow",
            tags=["growth-review"],
            workflow="growth_coach",
            today=target.isoformat(),
            domain="growth",
            stage="active",
            model=model_config.model,
        )
        content = render_frontmatter(metadata, parsed.body)

    output_path = write_note_safely(vault_path, relative_path, content, overwrite=True)
    return GrowthCoachResult(
        output_path=output_path,
        content=content,
        recent_note_count=len(recent_notes),
        latest_weekly_review_path=latest_weekly_review.path if latest_weekly_review else None,
        created_profile_templates=created_profile_templates,
        created_growth_templates=created_growth_templates,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an Obsidian growth coach review")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt without calling the LLM")
    args = parser.parse_args()

    config = load_workflow_config("growth_coach")
    result = run_growth_coach(
        vault_path=config.vault_path,
        model_config=config.model,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(result.content)
        print(f"\n[DRY RUN] Would write: {result.output_path}")
    else:
        print(f"Wrote growth review: {result.output_path}")
    if result.created_profile_templates:
        print(f"Created {len(result.created_profile_templates)} missing Profile template(s).")
    if result.created_growth_templates:
        print(f"Created {len(result.created_growth_templates)} missing Growth template(s).")
    if result.latest_weekly_review_path:
        print(f"Used weekly review: {result.latest_weekly_review_path}")
    else:
        print("No weekly review found yet.")
    print(f"Reviewed {result.recent_note_count} recent note(s).")


if __name__ == "__main__":
    main()
