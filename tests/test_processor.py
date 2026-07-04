from src.processor import _build_prompt


def test_meeting_processor_prompt_includes_opportunity_sections():
    prompt = _build_prompt("We discussed a client gap.", "meeting.txt", "2026-06-19")

    assert "domain: meeting" in prompt
    assert "stage: processed" in prompt
    assert "## Opportunity Signals" in prompt
    assert "## Work Context" in prompt
    assert "## Stakeholders / People Mentioned" in prompt
    assert "## Open Loops" in prompt
    assert "## Possible Project Links" in prompt
