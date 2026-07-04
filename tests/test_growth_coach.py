from datetime import date, datetime, timezone

from src.config import ModelConfig
from src.vault import VaultNote
from src.workflows.growth_coach import (
    build_growth_coach_prompt,
    growth_review_relative_path,
    run_growth_coach,
)


def test_growth_review_relative_path_uses_iso_week():
    assert growth_review_relative_path(date(2026, 6, 14)) == "Growth/Growth Reviews/2026-W24.md"


def test_build_growth_coach_prompt_includes_profile_review_growth_and_recent_notes(tmp_path):
    weekly = VaultNote(
        path=tmp_path / "Reviews" / "Weekly" / "2026-W24.md",
        relative_path="Reviews/Weekly/2026-W24.md",
        modified_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        content="Presence and design judgment showed up this week.",
    )
    recent = VaultNote(
        path=tmp_path / "Ideas" / "football.md",
        relative_path="Ideas/football.md",
        modified_at=datetime(2026, 6, 13, tzinfo=timezone.utc),
        content="Practice football warm-up drills before Monday.",
    )

    prompt = build_growth_coach_prompt(
        profile_notes={"Profile/Long-Term Goals.md": "# Long-Term Goals\n- Become more authoritative"},
        growth_notes={"Growth/Experiments.md": "# Experiments\n- [ ] Pause after one clear point"},
        latest_weekly_review=weekly,
        recent_notes=[recent],
        target_date=date(2026, 6, 14),
    )

    assert "Become more authoritative" in prompt
    assert "Pause after one clear point" in prompt
    assert "Presence and design judgment" in prompt
    assert "football warm-up drills" in prompt
    assert "Distinguish personal practice, projects, knowledge, and perspective" in prompt
    assert "opportunity signals in recent meeting notes" in prompt
    assert "# Growth Review - 2026-W24" in prompt


def test_run_growth_coach_dry_run_creates_templates_and_does_not_write_review(tmp_path):
    capture = tmp_path / "Ideas" / "2026-06-13-presence.md"
    capture.parent.mkdir()
    capture.write_text("# Presence\nPractise one clear point, then pause.", encoding="utf-8")
    weekly = tmp_path / "Reviews" / "Weekly" / "2026-W24.md"
    weekly.parent.mkdir(parents=True)
    weekly.write_text("# Weekly Review - 2026-W24\nPresence was a theme.", encoding="utf-8")

    result = run_growth_coach(
        vault_path=tmp_path,
        model_config=ModelConfig(provider="google", model="unused", api_key="unused"),
        dry_run=True,
        target_date=date(2026, 6, 14),
        now=datetime.now(timezone.utc),
    )

    assert result.output_path == tmp_path / "Growth" / "Growth Reviews" / "2026-W24.md"
    assert not result.output_path.exists()
    assert (tmp_path / "Growth" / "Skill Gaps.md").exists()
    assert result.latest_weekly_review_path == weekly
    assert result.recent_note_count == 1
    assert "Practise one clear point" in result.content
