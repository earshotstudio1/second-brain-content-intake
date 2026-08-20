import pytest
from src.url_utils import extract_url, extract_context, detect_platform


class TestExtractUrl:
    def test_extracts_https_url(self):
        text = "Check this out https://www.instagram.com/reel/DVHTDqfj9QZ/"
        assert extract_url(text) == "https://www.instagram.com/reel/DVHTDqfj9QZ/"

    def test_returns_none_when_no_url(self):
        assert extract_url("just some text with no link") is None

    def test_extracts_first_url_when_multiple(self):
        text = "https://youtube.com/watch?v=abc and https://instagram.com/reel/xyz"
        assert extract_url(text) == "https://youtube.com/watch?v=abc"

    def test_extracts_url_only_message(self):
        assert extract_url("https://youtu.be/dQw4w9WgXcQ") == "https://youtu.be/dQw4w9WgXcQ"


class TestExtractContext:
    def test_removes_url_and_strips(self):
        text = "Use this framing https://instagram.com/reel/abc for the client deck"
        url = "https://instagram.com/reel/abc"
        assert extract_context(text, url) == "Use this framing  for the client deck".strip()

    def test_returns_empty_string_when_only_url(self):
        url = "https://instagram.com/reel/abc"
        assert extract_context(url, url) == ""

    def test_returns_full_text_when_url_is_none(self):
        text = "just a brain dump"
        assert extract_context(text, None) == "just a brain dump"


class TestDetectPlatform:
    def test_instagram_reel(self):
        assert detect_platform("https://www.instagram.com/reel/DVHTDqfj9QZ/") == "instagram"

    def test_instagram_post(self):
        assert detect_platform("https://www.instagram.com/p/abc123/") == "instagram"

    def test_youtube_full(self):
        assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"

    def test_youtube_short(self):
        assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"

    def test_youtube_shorts(self):
        assert detect_platform("https://youtube.com/shorts/D3LdwISThoc") == "youtube"

    def test_linkedin(self):
        assert detect_platform("https://www.linkedin.com/posts/chris-tottman_abc") == "linkedin"

    def test_generic_url(self):
        assert detect_platform("https://example.com/article") == "generic"

    def test_none_returns_generic(self):
        assert detect_platform(None) == "generic"

    def test_lookalike_domain_is_not_instagram(self):
        assert detect_platform("https://instagram.com.attacker.example/p/x") == "generic"

    def test_platform_name_in_path_is_not_the_platform(self):
        assert detect_platform("https://evil.example/instagram.com/p/x") == "generic"

    def test_platform_name_in_query_is_not_the_platform(self):
        assert detect_platform("https://evil.example/?next=https://youtube.com/x") == "generic"

    def test_platform_name_in_userinfo_is_not_the_platform(self):
        assert detect_platform("https://linkedin.com@evil.example/posts/x") == "generic"

    def test_suffix_lookalike_is_not_youtube(self):
        assert detect_platform("https://notyoutube.com/watch?v=x") == "generic"

    def test_uppercase_host_still_matches(self):
        assert detect_platform("https://WWW.Instagram.COM/p/abc") == "instagram"

    def test_malformed_url_returns_generic(self):
        assert detect_platform("not a url at all") == "generic"
