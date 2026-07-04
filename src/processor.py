"""
Transcript processor.
Reads a transcript file, builds the prompt, and calls the configured LLM.
The LLM provider and model are determined entirely by config — this module
does not import any provider SDK directly.
"""

from datetime import date
from pathlib import Path

from .config import Config
from .llm import call_llm

SYSTEM_PROMPT = """\
You are a second brain assistant that turns meeting and conversation transcripts \
into structured, operationally useful notes.

Rules:
- Be concise. Omit pleasantries, filler, and tangents.
- Only include what helps get work done.
- If a section has no genuine content, write exactly: "- None identified"
- Do not invent information not present in the transcript.
- Return ONLY the markdown note — no preamble, no commentary.\
"""


def _build_prompt(transcript: str, filename: str, today: str) -> str:
    return f"""\
Process this transcript into a structured Obsidian note.

FILENAME: {filename}
TODAY: {today}

TRANSCRIPT:
---
{transcript}
---

Return the note using EXACTLY this structure. Do not add, remove, or rename sections.

---
title: "{{inferred meeting or session title}}"
date: {{YYYY-MM-DD date of the meeting, or {today} if unknown}}
type: meeting-note
domain: meeting
area: work
stage: processed
source: transcript
workflow: transcript_processing
related_projects: []
related_opportunities: []
participants: []
schema: meeting-opportunity-v1
tags: [meeting-notes]
---

# {{Title}}

## Summary
{{3–5 sentences. What was this about, what was accomplished, and what matters most?}}

## Action Items
{{One per line. Format: "- [ ] {{action}} — {{owner if identifiable}}"}}

## Decisions Made
{{One per line. Concrete decisions or agreements reached.}}

## Opportunity Signals
{{One per line. Problems, needs, gaps, openings, or moments where Daniel may be able to add value.}}

## Work Context
{{One per line. Background, constraints, project context, or organisational context that may matter later.}}

## Stakeholders / People Mentioned
{{One per line. People, teams, organisations, roles, or decision-makers mentioned.}}

## Blockers / Risks
{{One per line. Anything that could slow progress or needs attention.}}

## Open Loops
{{One per line. Unresolved issues, unclear ownership, pending decisions, or loose ends.}}

## Possible Project Links
{{One per line. Existing or potential projects this meeting may connect to.}}

## Follow-ups / Open Questions
{{One per line. Things that need answering or chasing.}}

## Participants
{{Comma-separated names or roles mentioned in the transcript, or "Unknown"}}

---
*Processed: {today} · Source: `{filename}`*\
"""


def _read_transcript(path: Path) -> str:
    """Read transcript with UTF-16 BOM detection, then UTF-8, then latin-1 fallback."""
    raw = path.read_bytes()

    if raw[:2] in (b"\xfe\xff", b"\xff\xfe"):
        return raw.decode("utf-16")

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass

    return raw.decode("latin-1")


def process_transcript(path: Path, config: Config) -> str:
    """Process a transcript file and return the generated markdown note."""
    transcript_text = _read_transcript(path)
    today = date.today().isoformat()

    model_cfg = config.models["transcript_processing"]
    return call_llm(
        model_cfg,
        SYSTEM_PROMPT,
        _build_prompt(transcript_text, path.name, today),
    )
