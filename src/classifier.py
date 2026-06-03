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

_VALID_CATEGORIES = {"captures", "ideas", "knowledge", "inbox"}

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
- "category": one of "captures" | "ideas" | "knowledge" | "inbox"
  - captures: links, social media content, external resources
  - ideas: app ideas, product concepts, business opportunities
  - knowledge: mindset, frameworks, tactics, learning, strategies
  - inbox: personal brain dumps, mixed content, anything ambiguous
- "tags": list of 2-5 lowercase single-word tags
- "summary": 2-3 sentence explanation of the core idea
- "takeaways": list of 2-5 concrete bullet points
- "how_to_use": the user's context note verbatim if provided, else empty string

Return ONLY the JSON object.\
"""


@dataclass
class ClassifiedCapture:
    title: str
    category: str                     # "captures" | "ideas" | "knowledge" | "inbox"
    tags: list[str]
    summary: str
    takeaways: list[str]
    how_to_use: str
    source_type: str                  # "instagram" | "youtube" | "linkedin" | "text" | "voice" | "generic"
    url: Optional[str]
    raw_content: str


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

    return ClassifiedCapture(
        title=str(data.get("title", "Untitled capture")).strip(),
        category=category,
        tags=[str(t).lower() for t in data.get("tags", [])],
        summary=str(data.get("summary", "")).strip(),
        takeaways=[str(t) for t in data.get("takeaways", [])],
        how_to_use=str(data.get("how_to_use", "")).strip(),
        source_type=source_type,
        url=url,
        raw_content=raw_content,
    )


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
    )
