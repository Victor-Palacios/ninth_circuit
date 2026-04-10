"""Unit tests — pure functions, no mocks needed."""

from datetime import datetime

from pipeline.fetch import _extract_case_number_from_url, _parse_date_from_description
from pipeline.extract import _strip_reasoning_and_fences
from pipeline.backfill import date_to_publish_ts
from pipeline.qa_check import _disposition_keywords


class TestExtractCaseNumberFromUrl:
    def test_standard_url(self):
        url = "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf"
        assert _extract_case_number_from_url(url) == "25-5185"

    def test_longer_case_number(self):
        url = "https://cdn.ca9.uscourts.gov/datastore/memoranda/2025/01/02/20-73521.pdf"
        assert _extract_case_number_from_url(url) == "20-73521"

    def test_no_match_returns_none(self):
        assert _extract_case_number_from_url("https://example.com/not-a-case.html") is None

    def test_empty_string(self):
        assert _extract_case_number_from_url("") is None


class TestParseDateFromDescription:
    def test_standard_date(self):
        assert _parse_date_from_description("Date Filed 03/13/2026") == "2026-03-13"

    def test_date_embedded_in_text(self):
        desc = "Some text Date Filed 12/01/2025 more text"
        assert _parse_date_from_description(desc) == "2025-12-01"

    def test_no_date_returns_none(self):
        assert _parse_date_from_description("No date here") is None

    def test_empty_string(self):
        assert _parse_date_from_description("") is None


class TestStripReasoningAndFences:
    def test_strips_think_block_and_json_fences(self):
        raw = '<think>some reasoning</think>\n```json\n{"key": "value"}\n```'
        assert _strip_reasoning_and_fences(raw) == '{"key": "value"}'

    def test_strips_only_fences(self):
        raw = '```json\n{"a": 1}\n```'
        assert _strip_reasoning_and_fences(raw) == '{"a": 1}'

    def test_no_fences_passthrough(self):
        raw = '{"a": 1}'
        assert _strip_reasoning_and_fences(raw) == '{"a": 1}'

    def test_strips_plain_backtick_fences(self):
        raw = '```\n{"b": 2}\n```'
        assert _strip_reasoning_and_fences(raw) == '{"b": 2}'


class TestDateToPublishTs:
    def test_known_date(self):
        dt = datetime(2026, 3, 14)
        assert date_to_publish_ts(dt) == 20260314000000

    def test_new_years(self):
        dt = datetime(2025, 1, 1)
        assert date_to_publish_ts(dt) == 20250101000000


class TestDispositionKeywords:
    def test_denied(self):
        result = _disposition_keywords("Denied")
        assert "denied" in result
        assert "petition for review is denied" in result

    def test_granted(self):
        result = _disposition_keywords("Granted")
        assert "granted" in result

    def test_none_returns_empty(self):
        assert _disposition_keywords(None) == []

    def test_unknown_disposition_falls_back(self):
        result = _disposition_keywords("SomeOtherOutcome")
        assert result == ["someotheroutcome"]
