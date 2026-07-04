from datetime import date, datetime, timezone

from src.config import ModelConfig
from src.vault import VaultNote
from src.workflows.weekly_review import (
    build_weekly_review_prompt,
    run_weekly_review,
    weekly_review_relative_path,
)


def test_weekly_review_relative_path_uses_iso_week():
    assert weekly_review_relative_path(date(2026, 6, 14)) == "Reviews/Weekly/2026-W24.md"


def test_build_weekly_review_prompt_includes_profile_and_recent_notes(tmp_path):
    note_path = tmp_path / "Captures" / "note.md"
    note = VaultNote(
        path=note_path,
        relative_path="Captures/note.md",
        modified_at=datetime(2026, 6, 13, tzinfo=timezone.utc),
        content="A useful capture about executive presence.",
    )

    prompt = build_weekly_review_prompt(
        profile_notes={"Profile/Long-Term Goals.md": "# Long-Term Goals\n- Become sharper"},
        recent_notes=[note],
        target_date=date(2026, 6, 14),
    )

    assert "Profile/Long-Term Goals.md" in prompt
    assert "Captures/note.md" in prompt
    assert "executive presence" in prompt
    assert "opportunity signals in recent meeting notes" in prompt
    assert "personal practice ideas worth trying" in prompt
    assert "# Weekly Review - 2026-W24" in prompt


def test_run_weekly_review_dry_run_creates_templates_and_does_not_write_review(tmp_path):
    capture = tmp_path / "Captures" / "presence.md"
    capture.parent.mkdir()
    capture.write_text("# Presence\nPractise one clear point, then pause.", encoding="utf-8")

    result = run_weekly_review(
        vault_path=tmp_path,
        model_config=ModelConfig(provider="google", model="unused", api_key="unused"),
        dry_run=True,
        target_date=date(2026, 6, 14),
        now=datetime.now(timezone.utc),
    )

    assert result.output_path == tmp_path / "Reviews" / "Weekly" / "2026-W24.md"
    assert not result.output_path.exists()
    assert (tmp_path / "Profile" / "Long-Term Goals.md").exists()
    assert result.recent_note_count == 1
    assert "Practise one clear point" in result.content
