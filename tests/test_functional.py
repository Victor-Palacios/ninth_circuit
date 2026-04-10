"""Functional tests — single functions with mocked I/O."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pipeline.fetch import parse_rss
from pipeline.classify_free import classify_opinion
from pipeline.classify_shared import insert_into_asylum_cases
from pipeline.qa_check import check_case


class TestParseRssReturnsOpinions:
    def test_returns_correct_opinions(self):
        fake_feed = SimpleNamespace(entries=[
            SimpleNamespace(
                link="https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
                title="Doe v. Garland",
                description="Date Filed 03/13/2026",
            ),
            SimpleNamespace(
                link="https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/12/24-1234.pdf",
                title="Smith v. Garland",
                description="Date Filed 03/12/2026",
            ),
        ])
        # feedparser returns an object; entries use attribute access via SimpleNamespace
        # but parse_rss uses entry.get(), so we need dicts
        fake_feed = SimpleNamespace(entries=[
            {"link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
             "title": "Doe v. Garland",
             "description": "Date Filed 03/13/2026"},
            {"link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/12/24-1234.pdf",
             "title": "Smith v. Garland",
             "description": "Date Filed 03/12/2026"},
        ])

        with patch("pipeline.fetch.feedparser.parse", return_value=fake_feed):
            result = parse_rss("https://fake.url/index.xml", "Published")

        assert len(result) == 2
        assert result[0]["case_number"] == "25-5185"
        assert result[0]["date_filed"] == "2026-03-13"
        assert result[0]["published_status"] == "Published"
        assert result[1]["case_number"] == "24-1234"


class TestClassifyOpinionReturnsTrue:
    def test_returns_true_for_asylum(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"reasoning": "asylum case", "answer": "yes"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("pipeline.classify_free.extract_text_from_pdf", return_value="This case involves asylum..."):
            result = classify_opinion(mock_client, "test-model", "https://fake.pdf")

        assert result is True


class TestClassifyOpinionReturnsFalse:
    def test_returns_false_for_non_asylum(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"reasoning": "tax dispute", "answer": "no"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("pipeline.classify_free.extract_text_from_pdf", return_value="This is a tax case..."):
            result = classify_opinion(mock_client, "test-model", "https://fake.pdf")

        assert result is False


class TestCheckCaseFindsKeywordDiscrepancy:
    def test_missing_country_flagged(self):
        row = {
            "country_of_origin": "Narnia",
            "country_of_origin_evidence": "Petitioner is from Narnia.",
            "final_disposition": "Denied",
            "final_disposition_evidence": "The petition is denied.",
            "asylum_requested": True,
            "asylum_requested_evidence": "Petitioner sought asylum.",
            "withholding_requested": False,
            "withholding_requested_evidence": "Not mentioned in the opinion.",
            "CAT_requested": False,
            "CAT_requested_evidence": "Not mentioned in the opinion.",
            "past_persecution_established": False,
            "past_persecution_established_evidence": "Not mentioned in the opinion.",
            "credibility_credibility_finding": False,
            "credibility_credibility_finding_evidence": "Not mentioned in the opinion.",
            "country_conditions_cited": False,
            "country_conditions_cited_evidence": "Not mentioned in the opinion.",
            "docket_no": "25-5185",
            "char_count": 5000,
        }
        # PDF text does NOT contain "Narnia"
        pdf_text = "This asylum case involves a petitioner from Guatemala. The petition is denied. Case 25-5185."

        discrepancies = check_case(row, pdf_text)
        country_issues = [d for d in discrepancies if d["field"] == "country_of_origin"]
        assert len(country_issues) == 1
        assert country_issues[0]["check_type"] == "keyword_match"


class TestInsertIntoAsylumCases:
    def test_upserts_with_correct_shape(self, fake_opinion, mock_supabase):
        insert_into_asylum_cases(mock_supabase, fake_opinion)

        mock_supabase.table.assert_called_with("asylum_cases")
        call_args = mock_supabase.table.return_value.upsert.call_args
        row = call_args[0][0]
        assert row["link"] == fake_opinion["link"]
        assert row["published_status"] == "Published"
        assert row["date_filed"] == "2026-03-13"
        assert row["docket_no"] == "25-5185"
