"""Integration tests — cross-module data flow with real internal logic.

Only true external boundaries (HTTP, database SDK) are mocked.
Internal functions run for real to verify data flows correctly between modules.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pipeline.fetch import parse_rss, fetch_today
from pipeline.classify_shared import insert_into_asylum_cases
from pipeline.qa_check import check_case


class TestFetchThenClassifyPipeline:
    """Real parse_rss output feeds real classify_opinion logic."""

    def test_fetch_output_shape_feeds_classify(self):
        fake_feed = SimpleNamespace(entries=[
            {"link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
             "title": "Doe v. Garland",
             "description": "Date Filed 03/13/2026"},
        ])

        with patch("pipeline.fetch.feedparser.parse", return_value=fake_feed):
            opinions = parse_rss("https://fake.url/index.xml", "Published")

        # Real parse_rss output should have the keys classify_opinion needs
        opinion = opinions[0]
        assert "link" in opinion
        assert opinion["link"].endswith(".pdf")

        # Now feed this opinion through real insert_into_asylum_cases
        mock_sb = MagicMock()
        insert_into_asylum_cases(mock_sb, opinion)

        # Verify the upsert was called with the right data
        upsert_call = mock_sb.table.return_value.upsert.call_args[0][0]
        assert upsert_call["link"] == opinion["link"]
        assert upsert_call["docket_no"] == opinion["case_number"]
        assert upsert_call["date_filed"] == opinion["date_filed"]


class TestClassifyThenExtractPipeline:
    """Row inserted by classify_shared matches the shape extract expects."""

    def test_classify_insert_shape_matches_extract_query(self):
        opinion = {
            "link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
            "case_title": "Doe v. Garland",
            "case_number": "25-5185",
            "date_filed": "2026-03-13",
            "published_status": "Published",
        }

        # Real insert_into_asylum_cases builds the row
        mock_sb = MagicMock()
        insert_into_asylum_cases(mock_sb, opinion)

        # Extract the row that was upserted
        inserted_row = mock_sb.table.return_value.upsert.call_args[0][0]

        # extract.fetch_pending_rows queries asylum_cases by link where char_count IS NULL
        # The inserted row should have "link" (the PK) and no "char_count" (not yet extracted)
        assert "link" in inserted_row
        assert "char_count" not in inserted_row  # not set until extraction runs


class TestExtractThenQaCheck:
    """Real extraction output dict passed through real check_case validation.
    No mocks — pure data flow test."""

    def test_valid_extraction_passes_qa(self):
        # Simulate a fully extracted row (what extract.run would produce)
        extracted_row = {
            "link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
            "docket_no": "25-5185",
            "country_of_origin": "Guatemala",
            "country_of_origin_evidence": "Petitioner is from Guatemala.",
            "final_disposition": "Denied",
            "final_disposition_evidence": "The petition for review is denied.",
            "asylum_requested": True,
            "asylum_requested_evidence": "Petitioner sought asylum under 8 U.S.C. § 1158.",
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
            "char_count": 8500,
        }

        # PDF text that matches the extracted fields — length must be close
        # to char_count (within 15% drift threshold) to avoid char_count_drift
        base_text = (
            "UNITED STATES COURT OF APPEALS FOR THE NINTH CIRCUIT\n"
            "No. 25-5185\n"
            "Petitioner is a native and citizen of Guatemala. "
            "Petitioner sought asylum under 8 U.S.C. § 1158. "
            "The petition for review is DENIED. "
        )
        # Pad to match char_count
        pdf_text = base_text + "x" * (8500 - len(base_text))

        # Real check_case should find no discrepancies
        discrepancies = check_case(extracted_row, pdf_text)
        assert discrepancies == []


class TestFetchDeduplicatesAcrossFeeds:
    """Real fetch_today dedup logic with real parse_rss; only HTTP and DB mocked."""

    @patch("pipeline.fetch.get_client")
    @patch("pipeline.fetch.feedparser.parse")
    def test_same_link_in_both_feeds_deduped(self, mock_feedparser, mock_get_client):
        shared_link = "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-9999.pdf"

        # Both feeds return the same link
        feed_published = SimpleNamespace(entries=[
            {"link": shared_link, "title": "Doe v. Garland (Published)", "description": "Date Filed 03/13/2026"},
        ])
        feed_unpublished = SimpleNamespace(entries=[
            {"link": shared_link, "title": "Doe v. Garland (Unpublished)", "description": "Date Filed 03/13/2026"},
        ])
        mock_feedparser.side_effect = [feed_published, feed_unpublished]

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [{"link": shared_link}]
        mock_get_client.return_value = mock_sb

        result = fetch_today(scrape_html=False)

        # Should have called upsert with exactly 1 opinion (deduplicated)
        upsert_call = mock_sb.table.return_value.upsert.call_args[0][0]
        assert len(upsert_call) == 1
        assert upsert_call[0]["link"] == shared_link


class TestConfigSupabaseClientWiring:
    """Real config module reads real env vars, passes to real create_client.
    Only supabase.create_client mocked at the SDK boundary."""

    def test_env_vars_reach_create_client(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://integration-test.supabase.co")
        monkeypatch.setenv("SUPABASE_SECRET_KEY", "integration-test-key")

        # Reload config first so it picks up the new env vars
        import importlib
        import lib.config
        importlib.reload(lib.config)

        # Reload supabase_client so it re-imports the reloaded config values
        import lib.supabase_client
        importlib.reload(lib.supabase_client)

        # Now patch create_client on the reloaded module
        with patch.object(lib.supabase_client, "create_client", return_value=MagicMock()) as mock_create:
            lib.supabase_client.get_client()
            mock_create.assert_called_once_with(
                "https://integration-test.supabase.co",
                "integration-test-key",
            )
