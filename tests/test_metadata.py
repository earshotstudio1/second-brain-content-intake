from datetime import date

from src.metadata import (
    build_metadata,
    infer_metadata,
    parse_frontmatter,
    render_frontmatter,
    stable_source_id,
)


def test_parse_and_render_frontmatter_preserves_body():
    content = """\
---
title: Existing
tags:
- one
---

# Existing

Body text.
"""

    parsed = parse_frontmatter(content)
    rendered = render_frontmatter(parsed.metadata, parsed.body)

    assert parsed.metadata["title"] == "Existing"
    assert "# Existing\n\nBody text." in rendered


def test_infer_metadata_adds_missing_fields_without_overwriting():
    existing = {
        "title": "User Title",
        "type": "custom-type",
        "source": "instagram",
        "url": "https://example.com/post",
    }

    metadata, fixes = infer_metadata(
        existing,
        "Knowledge/2026-06-13-Example.md",
        "# Body Title\nBody",
        now=date(2026, 6, 13),
    )

    assert metadata["title"] == "User Title"
    assert metadata["type"] == "custom-type"
    assert metadata["source"] == "instagram"
    assert metadata["date"] == "2026-06-13"
    assert metadata["status"] == "active"
    assert metadata["source_url"] == "https://example.com/post"
    assert metadata["source_id"] == stable_source_id("https://example.com/post")
    assert {fix.field for fix in fixes} >= {"date", "status", "source_url", "source_id"}


def test_infer_metadata_by_folder():
    metadata, _ = infer_metadata(
        {},
        "Meetings/2026-04-08-MDP-Meeting.md",
        "# MDP Meeting\nBody",
        now=date(2026, 6, 13),
    )

    assert metadata["title"] == "MDP Meeting"
    assert metadata["type"] == "meeting-note"
    assert metadata["domain"] == "meeting"
    assert metadata["stage"] == "processed"
    assert metadata["source"] == "transcript"
    assert metadata["workflow"] == "transcript_processing"


def test_build_metadata_supports_domain_stage_and_related_fields():
    metadata = build_metadata(
        title="Highlights Bot",
        note_type="project-idea",
        source="voice",
        tags=["football"],
        workflow="capture_telegram",
        today="2026-06-14",
        domain="project",
        area="app",
        stage="developing",
        decision="undecided",
        effort="medium",
        impact="high",
        confidence="medium",
        next_action="Sketch the MVP",
        review_after="2026-07-01",
        project_id="football-highlights",
        related_notes=["Personal/Practice/Football/drills.md"],
        related_projects=[],
        related_opportunities=[],
        participants=[],
    )

    assert metadata["domain"] == "project"
    assert metadata["area"] == "app"
    assert metadata["stage"] == "developing"
    assert metadata["decision"] == "undecided"
    assert metadata["next_action"] == "Sketch the MVP"
    assert metadata["related_notes"] == ["Personal/Practice/Football/drills.md"]


def test_infer_metadata_for_new_taxonomy_paths():
    metadata, _ = infer_metadata(
        {},
        "Personal/Practice/Football/2026-06-13-Drills.md",
        "# Drills\nBody",
        now=date(2026, 6, 13),
    )

    assert metadata["type"] == "practice-note"
    assert metadata["domain"] == "personal-practice"
    assert metadata["area"] == "football"
    assert metadata["stage"] == "to-try"
