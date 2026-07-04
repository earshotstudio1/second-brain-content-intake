from datetime import datetime, timezone

from src.workflows.domain_migration import migrate_idea_notes


def test_migrate_idea_notes_preserves_body_and_creates_backup_and_changelog(tmp_path):
    football = tmp_path / "Ideas" / "2026-06-13-Football-warm-up-drills-for-skill-and-technique-practice.md"
    app = tmp_path / "Ideas" / "2026-06-14-AppBot-for-Football-Highlights.md"
    football.parent.mkdir(parents=True)
    football.write_text("---\ntitle: Football drills\ntype: idea\n---\n\n# Football drills\n\nBody stays.", encoding="utf-8")
    app.write_text("---\ntitle: Highlights bot\ntype: idea\n---\n\n# Highlights bot\n\nBody also stays.", encoding="utf-8")

    results = migrate_idea_notes(
        tmp_path,
        apply=True,
        now=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
    )

    football_destination = tmp_path / "Personal" / "Practice" / "Football" / football.name
    app_destination = tmp_path / "Projects" / "Ideas" / app.name

    assert [result.status for result in results] == ["migrated", "migrated"]
    assert not football.exists()
    assert not app.exists()
    assert football_destination.exists()
    assert app_destination.exists()
    assert "# Football drills\n\nBody stays." in football_destination.read_text(encoding="utf-8")
    assert "type: practice-note" in football_destination.read_text(encoding="utf-8")
    assert "domain: personal-practice" in football_destination.read_text(encoding="utf-8")
    assert "area: football" in football_destination.read_text(encoding="utf-8")
    assert "type: project-idea" in app_destination.read_text(encoding="utf-8")
    assert "decision: undecided" in app_destination.read_text(encoding="utf-8")
    assert (tmp_path / ".second-brain" / "backups" / "domain-migration-20260619-120000" / "Ideas" / football.name).exists()
    assert (tmp_path / "Maintenance" / "Change Log" / "2026-06.md").exists()


def test_migrate_idea_notes_dry_run_does_not_move(tmp_path):
    football = tmp_path / "Ideas" / "2026-06-13-Football-warm-up-drills-for-skill-and-technique-practice.md"
    football.parent.mkdir(parents=True)
    football.write_text("# Football drills", encoding="utf-8")

    results = migrate_idea_notes(
        tmp_path,
        apply=False,
        now=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert results[0].status == "would-migrate"
    assert football.exists()
