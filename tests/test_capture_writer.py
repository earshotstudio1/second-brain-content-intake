import pytest
from pathlib import Path
from datetime import date
from src.classifier import ClassifiedCapture
from src.capture_writer import write_capture_note, _build_note_content


class TestBuildNoteContent:
    def _make_capture(self, **overrides) -> ClassifiedCapture:
        defaults = dict(
            title="Test Title",
            category="knowledge",
            tags=["ai", "strategy"],
            summary="This is the summary.",
            takeaways=["Point one", "Point two"],
            how_to_use="Use for client pitches",
            source_type="youtube",
            url="https://youtube.com/watch?v=abc",
            raw_content="raw transcript text here",
        )
        defaults.update(overrides)
        return ClassifiedCapture(**defaults)

    def test_contains_title_in_frontmatter(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert 'title: "Test Title"' in content

    def test_contains_tags(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "ai" in content

    def test_contains_summary(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "This is the summary." in content

    def test_contains_takeaways(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "Point one" in content

    def test_contains_how_to_use(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "Use for client pitches" in content

    def test_omits_how_to_use_section_when_empty(self):
        content = _build_note_content(self._make_capture(how_to_use=""), today="2026-06-01")
        assert "How I Want to Use This" not in content

    def test_contains_url(self):
        content = _build_note_content(self._make_capture(), today="2026-06-01")
        assert "https://youtube.com/watch?v=abc" in content


class TestWriteCaptureNote:
    def _make_capture(self, category="knowledge") -> ClassifiedCapture:
        return ClassifiedCapture(
            title="My Test Note",
            category=category,
            tags=["test"],
            summary="Summary here.",
            takeaways=["Point one"],
            how_to_use="",
            source_type="text",
            url=None,
            raw_content="raw text",
        )

    def test_writes_to_correct_folder(self, tmp_path):
        folders = {
            "captures": tmp_path / "Captures",
            "ideas": tmp_path / "Ideas",
            "knowledge": tmp_path / "Knowledge",
            "inbox": tmp_path / "Inbox",
        }
        for f in folders.values():
            f.mkdir()

        path = write_capture_note(self._make_capture(category="knowledge"), folders)
        assert path.parent == folders["knowledge"]

    def test_file_has_md_extension(self, tmp_path):
        folders = {"knowledge": tmp_path / "Knowledge"}
        folders["knowledge"].mkdir()
        path = write_capture_note(self._make_capture(category="knowledge"), folders)
        assert path.suffix == ".md"

    def test_unknown_category_falls_back_to_inbox(self, tmp_path):
        folders = {
            "inbox": tmp_path / "Inbox",
        }
        folders["inbox"].mkdir()
        path = write_capture_note(self._make_capture(category="unknown"), folders)
        assert path.parent == folders["inbox"]
