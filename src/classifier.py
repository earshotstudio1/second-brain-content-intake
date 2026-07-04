"""
Content classifier.
Sends fetched content to Gemini Flash and returns a ClassifiedCapture
with category, title, tags, summary, takeaways, and how_to_use.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import ModelConfig

_VALID_CATEGORIES = {
    "captures",
    "ideas",
    "knowledge",
    "inbox",
    "personal_practice",
    "project_idea",
    "knowledge_framework",
    "knowledge_best_practice",
    "knowledge_reference",
    "knowledge_tool",
    "perspective",
}

_SYSTEM_PROMPT = """\
You are a second-brain assistant that classifies and structures captured content.
You always return valid JSON and nothing else — no preamble, no markdown fences.\
"""

_USER_PROMPT_TEMPLATE = """\
Classify and structure the following captured content.

SOURCE TYPE: {source_type}
URL: {url}
USER CONTEXT NOTE: {context_note}

CONTENT:
---
{content}
---

Return a single JSON object with exactly these keys:
- "title": short descriptive title (max 10 words)
- "category": one of "personal_practice" | "project_idea" | "knowledge_framework" | "knowledge_best_practice" | "knowledge_reference" | "knowledge_tool" | "perspective" | "inbox"
  - personal_practice: drills, exercises, techniques, workouts, or habits the user wants to try personally
  - project_idea: app ideas, agent ideas, workflow ideas, product concepts, or business opportunities
  - knowledge_framework: reusable models, mental models, strategy frameworks, or operating systems
  - knowledge_best_practice: tactics, playbooks, methods, or practical advice worth applying
  - knowledge_reference: external resources, links, facts, examples, or material to keep for reference
  - knowledge_tool: tools, software, services, libraries, or products to evaluate
  - perspective: reflections, mindset, emotional concepts, values, relationships, or life lessons
  - inbox: mixed content, unclear intent, or anything ambiguous
- "area": short lowercase area when clear; examples: football, guitar, fitness, communication, mindset, app, agent, workflow, work, emotional-concepts, life-lessons, relationships, values. Use "" if unclear.
- "tags": list of 2-5 lowercase single-word tags
- "summary": 2-3 sentence explanation of the core idea
- "takeaways": list of 2-5 concrete bullet points
- "how_to_use": the user's context note verbatim if provided, else empty string

Return ONLY the JSON object.\
"""


@dataclass
class ClassifiedCapture:
    title: str
    category: str
    tags: list[str]
    summary: str
    takeaways: list[str]
    how_to_use: str
    source_type: str                  # "instagram" | "youtube" | "linkedin" | "text" | "voice" | "generic"
    url: Optional[str]
    raw_content: str
    area: str = ""


def classify(
    content: str,
    context_note: str,
    source_type: str,
    url: Optional[str],
    model_config: "ModelConfig",
) -> ClassifiedCapture:
    """Send content to Gemini and return a ClassifiedCapture."""
    from src.llm import call_llm

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        source_type=source_type,
        url=url or "none",
        context_note=context_note or "none",
        content=content[:8000],  # Guard against very long content
    )

    raw_response = call_llm(model_config, _SYSTEM_PROMPT, user_prompt)
    return _parse_classifier_response(raw_response, source_type=source_type, url=url, raw_content=content)


def _parse_classifier_response(
    raw: str,
    source_type: str,
    url: Optional[str],
    raw_content: str = "",
) -> ClassifiedCapture:
    """
    Parse the LLM JSON response into a ClassifiedCapture.
    Falls back to an inbox entry if parsing fails.
    """
    # Strip markdown code fences if the model wrapped the JSON
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()

    # Extract the first JSON object in case the model added preamble/postamble text
    json_match = re.search(r"\{[\s\S]*\}", cleaned)
    if json_match:
        cleaned = json_match.group(0)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return _fallback_capture(source_type, url, raw_content)

    category = data.get("category", "inbox")
    if category not in _VALID_CATEGORIES:
        category = "inbox"

    title = str(data.get("title", "Untitled capture")).strip()
    summary = str(data.get("summary", "")).strip()
    raw_tags = data.get("tags", [])
    tags = [str(t).lower() for t in raw_tags]
    area = str(data.get("area") or "").strip().lower()
    if not area:
        area = infer_area(" ".join([title, summary, raw_content, " ".join(tags)]), category)

    return ClassifiedCapture(
        title=title,
        category=category,
        area=area,
        tags=tags,
        summary=summary,
        takeaways=[str(t) for t in data.get("takeaways", [])],
        how_to_use=str(data.get("how_to_use", "")).strip(),
        source_type=source_type,
        url=url,
        raw_content=raw_content,
    )


def infer_area(text: str, category: str) -> str:
    """Infer a lightweight domain area from obvious content signals."""
    haystack = text.lower()
    keyword_areas = [
        ("football", ["football", "drill", "match", "warm-up", "warmup"]),
        ("guitar", ["guitar", "chord", "strumming", "riff"]),
        ("fitness", ["workout", "fitness", "gym", "run", "strength", "mobility"]),
        ("communication", ["speaking", "presence", "presentation", "conversation", "communicate"]),
        ("app", ["app", "application", "mobile"]),
        ("agent", ["agent", "ai agent", "orchestrator"]),
        ("workflow", ["workflow", "automation", "process", "pipeline"]),
        ("work", ["client", "business", "meeting", "team", "stakeholder"]),
        ("emotional-concepts", ["emotion", "feeling", "anxiety", "confidence"]),
        ("life-lessons", ["lesson", "life", "experience"]),
        ("relationships", ["relationship", "friend", "family", "partner"]),
        ("values", ["value", "principle", "standard"]),
        ("mindset", ["mindset", "belief", "perspective", "identity"]),
    ]
    for area, keywords in keyword_areas:
        if any(keyword in haystack for keyword in keywords):
            return area
    if category == "perspective":
        return "mindset"
    return ""


def _fallback_capture(source_type: str, url: Optional[str], raw_content: str) -> ClassifiedCapture:
    return ClassifiedCapture(
        title="Uncategorised capture",
        category="inbox",
        tags=["needs-review"],
        summary="Could not classify this content automatically.",
        takeaways=[],
        how_to_use="",
        source_type=source_type,
        url=url,
        raw_content=raw_content,
        area="",
    )
