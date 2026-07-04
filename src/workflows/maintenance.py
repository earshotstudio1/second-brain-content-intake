"""Obsidian vault metadata maintenance workflow."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.config import load_maintenance_config
from src.metadata import (
    MetadataFix,
    infer_metadata,
    normalize_url,
    parse_frontmatter,
    render_frontmatter,
)
from src.vault import write_note_safely


SCAN_FOLDERS = [
    "Captures",
    "Ideas",
    "Personal",
    "Projects",
    "Knowledge",
    "Perspective",
    "Inbox",
    "Meetings",
    "Reviews",
    "Growth",
    "Maintenance",
    "Profile",
]
EXCLUDED_PARTS = {".obsidian", ".trash", ".second-brain"}
RUN_LOG = ".second-brain/maintenance_runs.jsonl"
REPORT_FOLDER = "Maintenance/Reports"
CHANGE_LOG_FOLDER = "Maintenance/Change Log"
BACKUP_ROOT = ".second-brain/backups"


@dataclass(frozen=True)
class NoteIssue:
    relative_path: str
    fixes: list[MetadataFix]


@dataclass(frozen=True)
class DuplicateGroup:
    key: str
    canonical_path: str
    duplicate_paths: list[str]


@dataclass
class MaintenanceResult:
    scanned_count: int = 0
    changed_count: int = 0
    issue_count: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    report_path: Path | None = None
    change_log_path: Path | None = None
    run_log_path: Path | None = None
    backup_dir: Path | None = None
    dry_run: bool = True


def iter_markdown_notes(vault_path: Path, folders: list[str] | None = None) -> list[Path]:
    """Return markdown files in configured content folders, excluding system folders."""
    selected_folders = folders or SCAN_FOLDERS
    notes: list[Path] = []
    for folder_name in selected_folders:
        folder = vault_path / folder_name
        if not folder.exists():
            continue
        for path in folder.rglob("*.md"):
            relative_parts = set(path.relative_to(vault_path).parts)
            if relative_parts & EXCLUDED_PARTS:
                continue
            notes.append(path)
    return sorted(notes)


def detect_duplicate_urls(note_records: list[tuple[Path, dict[str, Any]]], vault_path: Path) -> list[DuplicateGroup]:
    """Detect duplicate source URLs and recommend the oldest/shortest path as canonical."""
    by_url: dict[str, list[tuple[int, Path]]] = {}
    for index, (path, metadata) in enumerate(note_records):
        source_url = metadata.get("source_url") or metadata.get("url")
        if not source_url:
            continue
        by_url.setdefault(normalize_url(str(source_url)), []).append((index, path))

    groups: list[DuplicateGroup] = []
    for key, indexed_paths in by_url.items():
        if len(indexed_paths) < 2:
            continue
        ordered = [path for _, path in sorted(indexed_paths, key=lambda item: (item[1].stat().st_mtime, item[0], len(str(item[1])), str(item[1])))]
        canonical = ordered[0]
        groups.append(
            DuplicateGroup(
                key=key,
                canonical_path=canonical.relative_to(vault_path).as_posix(),
                duplicate_paths=[p.relative_to(vault_path).as_posix() for p in ordered[1:]],
            )
        )
    return groups


def run_maintenance(
    vault_path: Path,
    apply_safe_fixes: bool = False,
    today: date | None = None,
    now: datetime | None = None,
    folders: list[str] | None = None,
    report_folder: str = REPORT_FOLDER,
    change_log_folder: str = CHANGE_LOG_FOLDER,
    run_log: str = RUN_LOG,
    backup_root: str = BACKUP_ROOT,
) -> MaintenanceResult:
    """Scan the vault and optionally apply low-risk metadata fixes."""
    run_date = today or date.today()
    run_time = now or datetime.now(timezone.utc)
    result = MaintenanceResult(dry_run=not apply_safe_fixes)
    notes = iter_markdown_notes(vault_path, folders)
    result.scanned_count = len(notes)

    note_records: list[tuple[Path, dict[str, Any]]] = []
    issues: list[NoteIssue] = []
    backup_dir: Path | None = None

    for path in notes:
        relative_path = path.relative_to(vault_path).as_posix()
        original = path.read_text(encoding="utf-8")
        parsed = parse_frontmatter(original)
        metadata, safe_fixes = infer_metadata(parsed.metadata, relative_path, parsed.body, now=run_date)
        fixes = safe_fixes + _domain_specific_fixes(metadata, parsed.body)
        note_records.append((path, metadata))
        if fixes:
            issues.append(NoteIssue(relative_path=relative_path, fixes=fixes))
            if apply_safe_fixes and safe_fixes:
                if backup_dir is None:
                    backup_dir = _backup_dir(vault_path, run_time, backup_root)
                _backup_file(vault_path, path, backup_dir)
                path.write_text(render_frontmatter(metadata, parsed.body), encoding="utf-8")
                result.changed_count += 1

    result.issue_count = len(issues)
    result.backup_dir = backup_dir
    result.duplicate_groups = detect_duplicate_urls(note_records, vault_path)

    report = _render_report(run_date, result, issues)
    report_path = write_note_safely(vault_path, f"{report_folder}/{run_date.isoformat()}.md", report, overwrite=True)
    result.report_path = report_path

    if apply_safe_fixes:
        change_log = _render_change_log(run_time, issues, result)
        month = run_date.strftime("%Y-%m")
        change_log_path = _append_change_log(vault_path, f"{change_log_folder}/{month}.md", change_log)
        result.change_log_path = change_log_path

    result.run_log_path = _append_run_log(vault_path, result, run_time, run_log)
    return result


def _domain_specific_fixes(metadata: dict[str, Any], body: str) -> list[MetadataFix]:
    """Return report-only checks that should not rewrite note bodies or move notes."""
    fixes: list[MetadataFix] = []
    domain = metadata.get("domain")
    stage = metadata.get("stage")
    if domain == "project":
        if metadata.get("decision") in (None, ""):
            fixes.append(MetadataFix("decision", None, "undecided", "project notes should record a decision"))
        if stage == "active" and metadata.get("next_action") in (None, "", []):
            fixes.append(MetadataFix("next_action", None, None, "active project notes should have a next_action"))
        if stage == "awaiting-approval":
            fixes.append(MetadataFix("stage", "awaiting-approval", "review-needed", "project is awaiting explicit approval"))
    if domain == "personal-practice" and stage == "to-try":
        fixes.append(MetadataFix("stage", "to-try", "review-needed", "personal practice note is waiting to be tried or reviewed"))
    if (
        domain == "meeting"
        and metadata.get("workflow") == "transcript_processing"
        and metadata.get("schema") == "meeting-opportunity-v1"
        and "## Opportunity Signals" not in body
    ):
        fixes.append(MetadataFix("body", None, "Opportunity Signals", "new meeting note is missing Opportunity Signals section"))
    return fixes


def _backup_dir(vault_path: Path, run_time: datetime, backup_root: str) -> Path:
    stamp = run_time.strftime("%Y%m%d-%H%M%S")
    path = vault_path / backup_root / f"metadata-migration-{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_file(vault_path: Path, source: Path, backup_dir: Path) -> None:
    destination = backup_dir / source.relative_to(vault_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _render_report(run_date: date, result: MaintenanceResult, issues: list[NoteIssue]) -> str:
    mode = "Apply safe fixes" if not result.dry_run else "Dry run"
    lines = [
        f"# Maintenance Report - {run_date.isoformat()}",
        "",
        "## Summary",
        f"- Mode: {mode}",
        f"- Notes scanned: {result.scanned_count}",
        f"- Notes with metadata fixes: {result.issue_count}",
        f"- Notes changed: {result.changed_count}",
        f"- Duplicate URL groups: {len(result.duplicate_groups)}",
        "",
        "## Metadata Fixes",
    ]
    if issues:
        for issue in issues:
            fields = ", ".join(fix.field for fix in issue.fixes)
            lines.append(f"- {issue.relative_path}: {fields}")
    else:
        lines.append("- None identified")

    lines.extend(["", "## Duplicate URL Suggestions"])
    if result.duplicate_groups:
        for group in result.duplicate_groups:
            lines.append(f"- Canonical: {group.canonical_path}")
            lines.append(f"  URL: {group.key}")
            lines.append(f"  Duplicates: {', '.join(group.duplicate_paths)}")
    else:
        lines.append("- None identified")

    return "\n".join(lines) + "\n"


def _render_change_log(run_time: datetime, issues: list[NoteIssue], result: MaintenanceResult) -> str:
    lines = [
        f"## {run_time.isoformat()}",
        "",
        f"- Notes changed: {result.changed_count}",
    ]
    if result.backup_dir:
        lines.append(f"- Backup: {result.backup_dir}")
    if issues:
        for issue in issues:
            fields = ", ".join(fix.field for fix in issue.fixes)
            lines.append(f"- {issue.relative_path}: added/updated {fields}")
    else:
        lines.append("- No metadata changes")
    lines.append("")
    return "\n".join(lines)


def _append_change_log(vault_path: Path, relative_path: str, entry: str) -> Path:
    path = vault_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing.rstrip() + "\n\n" + entry, encoding="utf-8")
    else:
        title = f"# Maintenance Change Log - {Path(relative_path).stem}\n\n"
        path.write_text(title + entry, encoding="utf-8")
    return path


def _append_run_log(vault_path: Path, result: MaintenanceResult, run_time: datetime, run_log: str) -> Path:
    path = vault_path / run_log
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "run_at": run_time.isoformat(),
        "dry_run": result.dry_run,
        "scanned_count": result.scanned_count,
        "issue_count": result.issue_count,
        "changed_count": result.changed_count,
        "duplicate_group_count": len(result.duplicate_groups),
        "report_path": str(result.report_path) if result.report_path else None,
        "change_log_path": str(result.change_log_path) if result.change_log_path else None,
        "backup_dir": str(result.backup_dir) if result.backup_dir else None,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain Obsidian vault metadata and hygiene")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report without editing notes")
    parser.add_argument("--apply-safe-fixes", action="store_true", help="Apply low-risk metadata fixes")
    args = parser.parse_args()

    if args.dry_run and args.apply_safe_fixes:
        parser.error("Choose either --dry-run or --apply-safe-fixes, not both")
    apply_safe_fixes = args.apply_safe_fixes

    config = load_maintenance_config()
    result = run_maintenance(
        config.vault_path,
        apply_safe_fixes=apply_safe_fixes,
        folders=config.scan_folders,
        report_folder=config.report_folder,
        change_log_folder=config.change_log_folder,
        run_log=config.run_log,
        backup_root=config.backup_root,
    )
    print(f"Scanned {result.scanned_count} note(s).")
    print(f"Metadata issues: {result.issue_count}. Changed: {result.changed_count}.")
    print(f"Duplicate URL groups: {len(result.duplicate_groups)}.")
    if result.report_path:
        print(f"Report: {result.report_path}")
    if result.change_log_path:
        print(f"Change log: {result.change_log_path}")
    if result.backup_dir:
        print(f"Backup: {result.backup_dir}")


if __name__ == "__main__":
    main()
