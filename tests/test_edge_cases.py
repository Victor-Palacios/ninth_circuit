"""Edge case tests — boundary inputs and unusual conditions."""

from types import SimpleNamespace
from unittest.mock import patch

from pipeline.fetch import parse_rss, _extract_case_number_from_url


class TestParseRssEmptyFeed:
    def test_empty_feed_returns_empty_list(self):
        fake_feed = SimpleNamespace(entries=[])
        with patch("pipeline.fetch.feedparser.parse", return_value=fake_feed):
            result = parse_rss("https://fake.url/index.xml", "Published")
        assert result == []


class TestExtractCaseNumberUrlNoMatch:
    def test_html_url(self):
        assert _extract_case_number_from_url("https://example.com/not-a-case.html") is None

    def test_empty_string(self):
        assert _extract_case_number_from_url("") is None

    def test_directory_url(self):
        assert _extract_case_number_from_url("https://ca9.uscourts.gov/opinions/") is None

    def test_pdf_without_case_number_pattern(self):
        assert _extract_case_number_from_url("https://example.com/document.pdf") is None
