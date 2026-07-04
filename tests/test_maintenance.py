from datetime import date, datetime, timezone
import json

from src.workflows.maintenance import (
    detect_duplicate_urls,
    iter_markdown_notes,
    run_maintenance,
)


def test_iter_markdown_notes_excludes_system_folders(tmp_path):
    keep = tmp_path / "Knowledge" / "keep.md"
    ignored = tmp_path / ".second-brain" / "ignored.md"
    keep.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    keep.write_text("# Keep", encoding="utf-8")
    ignored.write_text("# Ignore", encoding="utf-8")

    notes = iter_markdown_notes(tmp_path, ["Knowledge", ".second-brain"])

    assert notes == [keep]


def test_duplicate_url_detection_recommends_canonical(tmp_path):
    first = tmp_path / "Knowledge" / "first.md"
    second = tmp_path / "Captures" / "second.md"
    for path in [first, second]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Note", encoding="utf-8")

    groups = detect_duplicate_urls(
        [
            (first, {"source_url": "https://example.com/a?b=2&a=1"}),
            (second, {"source_url": "https://example.com/a?a=1&b=2"}),
        ],
        tmp_path,
    )

    assert len(groups) == 1
    assert groups[0].canonical_path == "Knowledge/first.md"
    assert groups[0].duplicate_paths == ["Captures/second.md"]


def test_dry_run_reports_without_changing_source_note(tmp_path):
    note = tmp_path / "Knowledge" / "2026-06-13-Test.md"
    note.parent.mkdir(parents=True)
    original = "# Test\n\nBody stays."
    note.write_text(original, encoding="utf-8")

    result = run_maintenance(
        tmp_path,
        apply_safe_fixes=False,
        today=date(2026, 6, 13),
        now=datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc),
        folders=["Knowledge"],
    )

    assert note.read_text(encoding="utf-8") == original
    assert result.changed_count == 0
    assert result.report_path and result.report_path.exists()
    assert result.run_log_path and result.run_log_path.exists()


def test_apply_safe_fixes_creates_backup_logs_and_preserves_body(tmp_path):
    note = tmp_path / "Knowledge" / "2026-06-13-Test.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Test\n\nBody stays.", encoding="utf-8")

    result = run_maintenance(
        tmp_path,
        apply_safe_fixes=True,
        today=date(2026, 6, 13),
        now=datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc),
        folders=["Knowledge"],
    )

    content = note.read_text(encoding="utf-8")
    assert "status: active" in content
    assert "workflow: capture_telegram" in content
    assert "# Test\n\nBody stays." in content
    assert result.backup_dir is not None
    assert (result.backup_dir / "Knowledge" / "2026-06-13-Test.md").exists()
    assert result.change_log_path and result.change_log_path.exists()

    log_line = result.run_log_path.read_text(encoding="utf-8").strip().splitlines()[-1]
    log = json.loads(log_line)
    assert log["changed_count"] == 1


def test_iter_markdown_notes_scans_new_domain_folders(tmp_path):
    personal = tmp_path / "Personal" / "Practice" / "Football" / "drills.md"
    project = tmp_path / "Projects" / "Ideas" / "bot.md"
    perspective = tmp_path / "Perspective" / "Mindset" / "note.md"
    for path in [personal, project, perspective]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Note", encoding="utf-8")

    notes = iter_markdown_notes(tmp_path, ["Personal", "Projects", "Perspective"])

    assert notes == [personal, perspective, project]


def test_maintenance_flags_missing_domain_and_stage(tmp_path):
    note = tmp_path / "Projects" / "Ideas" / "2026-06-14-Bot.md"
    note.parent.mkdir(parents=True)
    note.write_text("---\ntitle: Bot\n---\n\n# Bot\n", encoding="utf-8")

    result = run_maintenance(
        tmp_path,
        apply_safe_fixes=False,
        today=date(2026, 6, 14),
        now=datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc),
        folders=["Projects"],
    )

    report = result.report_path.read_text(encoding="utf-8")
    assert result.issue_count == 1
    assert "domain" in report
    assert "stage" in report
    assert "decision" in report


def test_maintenance_reports_active_project_missing_next_action_without_writing(tmp_path):
    note = tmp_path / "Projects" / "Active" / "Active.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "---\ntitle: Active\ndate: 2026-06-14\ntype: project-note\ndomain: project\nstage: active\ndecision: approved\nsource: manual\nstatus: active\ntags: []\ncreated: 2026-06-14\nupdated: 2026-06-14\nworkflow: manual\n---\n\n# Active\n",
        encoding="utf-8",
    )
    original = note.read_text(encoding="utf-8")

    result = run_maintenance(
        tmp_path,
        apply_safe_fixes=True,
        today=date(2026, 6, 14),
        now=datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc),
        folders=["Projects"],
    )

    assert result.issue_count == 1
    assert result.changed_count == 0
    assert note.read_text(encoding="utf-8") == original
