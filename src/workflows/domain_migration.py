"""Safe one-off domain taxonomy migrations for the Obsidian vault."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import load_basic_config
from src.metadata import parse_frontmatter, render_frontmatter


BACKUP_ROOT = ".second-brain/backups"
CHANGE_LOG_FOLDER = "Maintenance/Change Log"


@dataclass(frozen=True)
class MigrationSpec:
    source: str
    destination: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MigrationResult:
    source: str
    destination: str
    status: str


IDEA_MIGRATIONS = [
    MigrationSpec(
        source="Ideas/2026-06-13-Football-warm-up-drills-for-skill-and-technique-practice.md",
        destination="Personal/Practice/Football/2026-06-13-Football-warm-up-drills-for-skill-and-technique-practice.md",
        metadata={
            "type": "practice-note",
            "domain": "personal-practice",
            "area": "football",
            "stage": "to-try",
            "status": "active",
        },
    ),
    MigrationSpec(
        source="Ideas/2026-06-14-AppBot-for-Football-Highlights.md",
        destination="Projects/Ideas/2026-06-14-AppBot-for-Football-Highlights.md",
        metadata={
            "type": "project-idea",
            "domain": "project",
            "area": "app",
            "stage": "developing",
            "decision": "undecided",
            "status": "active",
        },
    ),
]


def migrate_idea_notes(
    vault_path: Path,
    apply: bool = False,
    now: datetime | None = None,
    migrations: list[MigrationSpec] | None = None,
) -> list[MigrationResult]:
    """Preview or apply the explicit Ideas/ migrations requested for this taxonomy slice."""
    run_time = now or datetime.now(timezone.utc)
    specs = migrations or IDEA_MIGRATIONS
    results: list[MigrationResult] = []
    backup_dir: Path | None = None

    for spec in specs:
        source = vault_path / spec.source
        destination = vault_path / spec.destination

        if not source.exists():
            status = "already-migrated" if destination.exists() else "missing-source"
            results.append(MigrationResult(spec.source, spec.destination, status))
            continue
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")

        results.append(MigrationResult(spec.source, spec.destination, "would-migrate" if not apply else "migrated"))
        if not apply:
            continue

        if backup_dir is None:
            backup_dir = _backup_dir(vault_path, run_time)
        _backup_file(vault_path, source, backup_dir)

        original = source.read_text(encoding="utf-8")
        parsed = parse_frontmatter(original)
        metadata = dict(parsed.metadata)
        metadata.update(spec.metadata)
        metadata["updated"] = run_time.date().isoformat()

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_frontmatter(metadata, parsed.body), encoding="utf-8")
        source.unlink()

    if apply and any(result.status == "migrated" for result in results):
        _append_change_log(vault_path, run_time, results, backup_dir)
    return results


def _backup_dir(vault_path: Path, run_time: datetime) -> Path:
    stamp = run_time.strftime("%Y%m%d-%H%M%S")
    path = vault_path / BACKUP_ROOT / f"domain-migration-{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _backup_file(vault_path: Path, source: Path, backup_dir: Path) -> None:
    destination = backup_dir / source.relative_to(vault_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _append_change_log(
    vault_path: Path,
    run_time: datetime,
    results: list[MigrationResult],
    backup_dir: Path | None,
) -> Path:
    month = run_time.strftime("%Y-%m")
    path = vault_path / CHANGE_LOG_FOLDER / f"{month}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"## {run_time.isoformat()}",
        "",
        "- Domain taxonomy migration applied.",
    ]
    if backup_dir:
        lines.append(f"- Backup: {backup_dir}")
    for result in results:
        if result.status == "migrated":
            lines.append(f"- Moved `{result.source}` -> `{result.destination}`")
    lines.append("")
    entry = "\n".join(lines)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        path.write_text(existing.rstrip() + "\n\n" + entry, encoding="utf-8")
    else:
        path.write_text(f"# Maintenance Change Log - {month}\n\n{entry}", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Ideas notes into the domain taxonomy")
    parser.add_argument("--apply", action="store_true", help="Apply the migration instead of previewing it")
    args = parser.parse_args()

    config = load_basic_config()
    results = migrate_idea_notes(config.vault_path, apply=args.apply)
    for result in results:
        print(f"{result.status}: {result.source} -> {result.destination}")


if __name__ == "__main__":
    main()
