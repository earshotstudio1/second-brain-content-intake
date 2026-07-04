"""Shared Obsidian frontmatter metadata helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml


STANDARD_FIELDS = [
    "title",
    "date",
    "type",
    "domain",
    "area",
    "stage",
    "decision",
    "effort",
    "impact",
    "confidence",
    "next_action",
    "review_after",
    "project_id",
    "related_notes",
    "related_projects",
    "related_opportunities",
    "participants",
    "source",
    "status",
    "tags",
    "source_url",
    "source_id",
    "created",
    "updated",
    "workflow",
    "model",
]

REQUIRED_FIELDS = [
    "title",
    "date",
    "type",
    "domain",
    "source",
    "status",
    "stage",
    "tags",
    "created",
    "updated",
    "workflow",
]


@dataclass(frozen=True)
class ParsedNote:
    metadata: dict[str, Any]
    body: str
    has_frontmatter: bool


@dataclass(frozen=True)
class MetadataFix:
    field: str
    old_value: Any
    new_value: Any
    reason: str


def parse_frontmatter(content: str) -> ParsedNote:
    """Parse YAML frontmatter, returning an empty metadata dict if absent."""
    if not content.startswith("---\n"):
        return ParsedNote(metadata={}, body=content, has_frontmatter=False)

    end = content.find("\n---", 4)
    if end == -1:
        return ParsedNote(metadata={}, body=content, has_frontmatter=False)

    raw_yaml = content[4:end]
    body_start = end + len("\n---")
    if content[body_start:body_start + 1] == "\n":
        body_start += 1
    raw_metadata = yaml.safe_load(raw_yaml) or {}
    if not isinstance(raw_metadata, dict):
        raw_metadata = {}
    return ParsedNote(metadata=dict(raw_metadata), body=content[body_start:], has_frontmatter=True)


def render_frontmatter(metadata: dict[str, Any], body: str) -> str:
    """Render flat, stable YAML frontmatter followed by the original note body."""
    ordered: dict[str, Any] = {}
    for field in STANDARD_FIELDS:
        if field in metadata and metadata[field] not in (None, ""):
            ordered[field] = metadata[field]
    for field, value in metadata.items():
        if field not in ordered and value not in (None, ""):
            ordered[field] = value

    frontmatter = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{body.lstrip()}"


def stable_source_id(value: str) -> str:
    """Return a short stable ID for a URL or source path."""
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()[:16]


def normalize_url(url: str) -> str:
    """Normalize a URL enough for duplicate detection without being clever."""
    parts = urlsplit(url.strip())
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        query,
        "",
    ))


def build_metadata(
    title: str,
    note_type: str,
    source: str,
    tags: list[str] | None,
    workflow: str,
    today: str | None = None,
    domain: str | None = None,
    stage: str | None = None,
    area: str | None = None,
    decision: str | None = None,
    effort: str | None = None,
    impact: str | None = None,
    confidence: str | None = None,
    next_action: str | None = None,
    review_after: str | None = None,
    project_id: str | None = None,
    related_notes: list[str] | None = None,
    related_projects: list[str] | None = None,
    related_opportunities: list[str] | None = None,
    participants: list[str] | None = None,
    source_url: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Create standard metadata for newly generated notes."""
    current_date = today or date.today().isoformat()
    metadata: dict[str, Any] = {
        "title": title,
        "date": current_date,
        "type": note_type,
        "domain": domain or _domain_from_type(note_type),
        "source": source,
        "status": "active",
        "stage": stage or _default_stage_for_domain(domain or _domain_from_type(note_type)),
        "tags": tags or [],
        "created": current_date,
        "updated": current_date,
        "workflow": workflow,
    }
    optional_fields = {
        "area": area,
        "decision": decision,
        "effort": effort,
        "impact": impact,
        "confidence": confidence,
        "next_action": next_action,
        "review_after": review_after,
        "project_id": project_id,
        "related_notes": related_notes,
        "related_projects": related_projects,
        "related_opportunities": related_opportunities,
        "participants": participants,
    }
    for field, value in optional_fields.items():
        if value not in (None, ""):
            metadata[field] = value
    if source_url:
        metadata["source_url"] = source_url
        metadata["source_id"] = stable_source_id(normalize_url(source_url))
    if model:
        metadata["model"] = model
    return metadata


def infer_metadata(
    existing: dict[str, Any],
    relative_path: str,
    body: str,
    now: date | None = None,
    model_by_workflow: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[MetadataFix]]:
    """Add missing practical-core metadata without overwriting existing values."""
    current_date = (now or date.today()).isoformat()
    metadata = dict(existing)
    fixes: list[MetadataFix] = []

    def add_missing(field: str, value: Any, reason: str) -> None:
        if field not in metadata or metadata[field] in (None, ""):
            metadata[field] = value
            fixes.append(MetadataFix(field, None, value, reason))

    source_url = metadata.get("source_url") or metadata.get("url")
    if source_url and "source_url" not in metadata:
        add_missing("source_url", str(source_url), "copied from existing url field")

    title = metadata.get("title") or _title_from_body(body) or Path(relative_path).stem
    add_missing("title", title, "inferred from heading or filename")
    add_missing("date", _date_from_path(relative_path) or current_date, "inferred from filename or run date")
    add_missing("type", _type_from_path(relative_path), "inferred from vault folder")
    domain = str(metadata.get("domain") or _domain_from_path(relative_path, metadata))
    add_missing("domain", domain, "inferred from vault folder/type")
    add_missing("stage", _stage_from_path(relative_path, metadata), "inferred from vault folder/domain")
    inferred_area = _area_from_path(relative_path)
    if inferred_area:
        add_missing("area", inferred_area, "inferred from vault subfolder")
    if domain == "project":
        add_missing("decision", "undecided", "default decision for project notes")
    add_missing("source", _source_from_path(relative_path, metadata), "inferred from note folder/type")
    add_missing("status", "active", "default active status")
    add_missing("tags", [], "default empty tag list")
    add_missing("created", str(metadata.get("date") or current_date), "inferred from note date")

    workflow = _workflow_from_path(relative_path, metadata)
    add_missing("workflow", workflow, "inferred from note folder/type")
    if source_url and "source_id" not in metadata:
        add_missing("source_id", stable_source_id(normalize_url(str(source_url))), "generated from source_url")

    if model_by_workflow and workflow in model_by_workflow and "model" not in metadata:
        add_missing("model", model_by_workflow[workflow], "inferred from workflow config")

    if fixes:
        metadata["updated"] = current_date
        if not any(f.field == "updated" for f in fixes):
            fixes.append(MetadataFix("updated", existing.get("updated"), current_date, "metadata autofix timestamp"))
    else:
        add_missing("updated", str(metadata.get("created") or current_date), "default updated date")

    return metadata, fixes


def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    """Return missing required metadata field names."""
    return [field for field in REQUIRED_FIELDS if field not in metadata or metadata[field] in (None, "")]


def _title_from_body(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or None
    return None


def _date_from_path(relative_path: str) -> str | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", relative_path)
    return match.group(1) if match else None


def _type_from_path(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    first = parts[0].lower()
    second = parts[1].lower() if len(parts) > 1 else ""
    if first == "personal" and second == "practice":
        return "practice-note"
    if first == "projects":
        return "project-idea" if second == "ideas" else "project-note"
    if first == "perspective":
        return "perspective-note"
    if first == "knowledge":
        return {
            "frameworks": "framework",
            "best practices": "best-practice",
            "references": "reference",
            "tools": "tool",
            "case studies": "case-study",
        }.get(second, "knowledge")
    return {
        "captures": "capture",
        "ideas": "idea",
        "knowledge": "knowledge",
        "inbox": "brain-dump",
        "meetings": "meeting-note",
        "daily": "daily-brief",
        "reviews": "review",
        "growth": "growth-note",
        "reports": "report",
        "profile": "profile",
        "personal": "practice-note",
        "projects": "project-note",
        "perspective": "perspective-note",
        "maintenance": "maintenance",
    }.get(first, "note")


def _domain_from_type(note_type: str) -> str:
    return {
        "practice-note": "personal-practice",
        "project-idea": "project",
        "project-note": "project",
        "framework": "knowledge",
        "best-practice": "knowledge",
        "reference": "knowledge",
        "tool": "knowledge",
        "case-study": "knowledge",
        "knowledge": "knowledge",
        "perspective-note": "perspective",
        "meeting-note": "meeting",
        "profile": "profile",
        "maintenance": "maintenance",
        "growth-note": "growth",
        "growth-review": "growth",
        "brain-dump": "inbox",
        "review": "growth",
        "daily-brief": "maintenance",
        "report": "maintenance",
    }.get(note_type, "inbox")


def _domain_from_path(relative_path: str, metadata: dict[str, Any]) -> str:
    if metadata.get("domain"):
        return str(metadata["domain"])
    normalized = relative_path.replace("\\", "/")
    first = normalized.split("/", 1)[0].lower()
    return {
        "personal": "personal-practice",
        "projects": "project",
        "ideas": "project",
        "knowledge": "knowledge",
        "perspective": "perspective",
        "meetings": "meeting",
        "profile": "profile",
        "maintenance": "maintenance",
        "growth": "growth",
        "inbox": "inbox",
        "captures": "inbox",
    }.get(first, _domain_from_type(str(metadata.get("type") or _type_from_path(relative_path))))


def _default_stage_for_domain(domain: str) -> str:
    return {
        "personal-practice": "inbox",
        "project": "inbox",
        "knowledge": "inbox",
        "perspective": "inbox",
        "meeting": "processed",
        "profile": "active",
        "maintenance": "active",
        "growth": "active",
        "inbox": "inbox",
    }.get(domain, "inbox")


def _stage_from_path(relative_path: str, metadata: dict[str, Any]) -> str:
    if metadata.get("stage"):
        return str(metadata["stage"])
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    first = parts[0].lower()
    second = parts[1].lower() if len(parts) > 1 else ""
    if first == "personal" and second == "practice":
        return "to-try"
    if first == "projects":
        return {
            "ideas": "developing",
            "awaiting approval": "awaiting-approval",
            "backlog": "backlog",
            "active": "active",
            "shipped": "shipped",
            "paused": "paused",
            "archive": "archived",
        }.get(second, "inbox")
    if first == "ideas":
        return "developing"
    if first == "knowledge":
        return "reference" if second == "references" else "active"
    if first == "perspective":
        return "reflecting"
    if first == "meetings":
        return "processed"
    return _default_stage_for_domain(_domain_from_path(relative_path, metadata))


def _area_from_path(relative_path: str) -> str | None:
    parts = relative_path.replace("\\", "/").split("/")
    if len(parts) < 3:
        return None
    first = parts[0].lower()
    second = parts[1].lower()
    if first == "personal" and second == "practice":
        return parts[2].lower()
    if first == "perspective":
        return parts[1].lower()
    if first == "meetings":
        return parts[1].lower()
    return None


def _source_from_path(relative_path: str, metadata: dict[str, Any]) -> str:
    if metadata.get("source"):
        return str(metadata["source"])
    note_type = metadata.get("type") or _type_from_path(relative_path)
    if note_type == "meeting-note":
        return "transcript"
    if note_type == "profile":
        return "manual"
    if note_type in ("review", "daily-brief", "growth-note", "report"):
        return "workflow"
    return "manual"


def _workflow_from_path(relative_path: str, metadata: dict[str, Any]) -> str:
    if metadata.get("workflow"):
        return str(metadata["workflow"])
    normalized = relative_path.replace("\\", "/")
    note_type = metadata.get("type") or _type_from_path(relative_path)
    if normalized.startswith(("Captures/", "Ideas/", "Personal/", "Projects/", "Knowledge/", "Perspective/", "Inbox/")):
        return "capture_telegram"
    if normalized.startswith("Meetings/") or note_type == "meeting-note":
        return "transcript_processing"
    if normalized.startswith("Reviews/Weekly/"):
        return "weekly_review"
    if normalized.startswith("Daily/"):
        return "daily_brief"
    if normalized.startswith("Growth/"):
        return "growth_coach"
    if normalized.startswith("Reports/Industry Briefs/"):
        return "industry_brief"
    if normalized.startswith("Profile/"):
        return "profile_template"
    return "manual"
