import pytest
from src.classifier import _parse_classifier_response, ClassifiedCapture


class TestParseClassifierResponse:
    def test_parses_valid_json(self):
        raw = '''{
            "title": "Jensen Huang on AI Agents",
            "category": "knowledge_framework",
            "area": "agent",
            "tags": ["ai", "strategy"],
            "summary": "Jensen talks about agentic AI.",
            "takeaways": ["Agents will replace SaaS", "Data is the moat"],
            "how_to_use": "Use for client positioning"
        }'''
        result = _parse_classifier_response(raw, source_type="youtube", url="https://youtu.be/abc")
        assert result.title == "Jensen Huang on AI Agents"
        assert result.category == "knowledge_framework"
        assert result.area == "agent"
        assert result.tags == ["ai", "strategy"]
        assert result.summary == "Jensen talks about agentic AI."
        assert result.takeaways == ["Agents will replace SaaS", "Data is the moat"]
        assert result.how_to_use == "Use for client positioning"
        assert result.source_type == "youtube"
        assert result.url == "https://youtu.be/abc"

    def test_strips_markdown_code_fence(self):
        raw = '```json\n{"title": "Test", "category": "inbox", "tags": [], "summary": "s", "takeaways": [], "how_to_use": ""}\n```'
        result = _parse_classifier_response(raw, source_type="text", url=None)
        assert result.title == "Test"

    def test_invalid_category_falls_back_to_inbox(self):
        raw = '{"title": "X", "category": "unknown_category", "tags": [], "summary": "s", "takeaways": [], "how_to_use": ""}'
        result = _parse_classifier_response(raw, source_type="text", url=None)
        assert result.category == "inbox"

    def test_json_parse_error_falls_back_to_inbox(self):
        result = _parse_classifier_response("not json at all", source_type="text", url=None)
        assert result.category == "inbox"
        assert result.title == "Uncategorised capture"

    def test_infers_area_for_personal_practice(self):
        raw = '{"title": "Football Warmups", "category": "personal_practice", "tags": ["football"], "summary": "Warm-up drills before matches.", "takeaways": [], "how_to_use": ""}'
        result = _parse_classifier_response(raw, source_type="voice", url=None)
        assert result.category == "personal_practice"
        assert result.area == "football"
