"""Application tests — higher-level workflow tests with external I/O mocked."""

import json
from unittest.mock import MagicMock, patch, mock_open

import pytest


class TestFetchTodayRssOnly:
    """fetch_today(scrape_html=False) parses RSS and inserts into Supabase."""

    @patch("pipeline.fetch.get_client")
    @patch("pipeline.fetch.parse_rss")
    def test_inserts_all_opinions(self, mock_parse_rss, mock_get_client):
        opinions = [
            {"link": "https://cdn.ca9.uscourts.gov/a.pdf", "case_title": "A", "case_number": "25-1",
             "date_filed": "2026-03-13", "published_status": "Published"},
            {"link": "https://cdn.ca9.uscourts.gov/b.pdf", "case_title": "B", "case_number": "25-2",
             "date_filed": "2026-03-13", "published_status": "Published"},
            {"link": "https://cdn.ca9.uscourts.gov/c.pdf", "case_title": "C", "case_number": "25-3",
             "date_filed": "2026-03-13", "published_status": "Unpublished"},
        ]
        mock_parse_rss.side_effect = [opinions[:2], [opinions[2]]]  # published, unpublished

        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value.data = opinions
        mock_get_client.return_value = mock_sb

        from pipeline.fetch import fetch_today
        count = fetch_today(scrape_html=False)

        assert count == 3
        mock_sb.table.assert_called_with("all_opinions")


class TestClassifyFreeRunProcessesPending:
    """classify_free.run() classifies pending opinions and updates DB."""

    @patch("pipeline.classify_free.insert_into_asylum_cases")
    @patch("pipeline.classify_free.classify_opinion")
    @patch("pipeline.classify_free.fetch_unclassified")
    @patch("pipeline.classify_free.get_client")
    def test_classifies_and_inserts(self, mock_get_client, mock_fetch, mock_classify,
                                     mock_insert, env_provider, tmp_path, monkeypatch):
        monkeypatch.setenv("CLASSIFY_SUMMARY_FILE", str(tmp_path / "summary.txt"))

        pending = [
            {"link": "https://a.pdf", "case_title": "A", "case_number": "25-1",
             "date_filed": "2026-01-01", "published_status": "Published"},
            {"link": "https://b.pdf", "case_title": "B", "case_number": "25-2",
             "date_filed": "2026-01-02", "published_status": "Published"},
        ]
        mock_sb = MagicMock()
        mock_get_client.return_value = mock_sb
        mock_fetch.return_value = pending
        mock_classify.side_effect = [True, False]  # first asylum, second not

        from pipeline.classify_free import run
        result = run()

        assert result == 2
        mock_insert.assert_called_once()  # only for the True case
        assert mock_sb.table.return_value.update.call_count == 2


class TestExtractRunOpenaiProvider:
    """extract.run(provider='openai') extracts features and updates DB."""

    @patch("pipeline.extract.mlflow")
    @patch("pipeline.extract.send_text_to_provider")
    @patch("pipeline.extract.pymupdf")
    @patch("pipeline.extract.download_pdf")
    @patch("pipeline.extract.fetch_pending_rows")
    @patch("pipeline.extract.get_client")
    def test_extracts_and_updates(self, mock_get_client, mock_fetch_pending,
                                   mock_download, mock_pymupdf, mock_send,
                                   mock_mlflow, env_provider, tmp_path, monkeypatch):
        monkeypatch.setenv("SUMMARY_FILE", str(tmp_path / "summary.txt"))

        mock_sb = MagicMock()
        mock_get_client.return_value = mock_sb
        mock_fetch_pending.return_value = [{"link": "https://fake.pdf"}]
        mock_download.return_value = b"fake-pdf-bytes"

        # Mock pymupdf document
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Full opinion text here about asylum."
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_pymupdf.open.return_value = mock_doc

        # Mock LLM response
        mock_send.return_value = {
            "country_of_origin": "Guatemala",
            "country_of_origin_evidence": "From Guatemala.",
            "asylum_requested": True,
            "asylum_requested_evidence": "Sought asylum.",
            "final_disposition": "Denied",
            "final_disposition_evidence": "Petition denied.",
        }

        # Mock mlflow context manager
        mock_mlflow.start_run.return_value.__enter__ = MagicMock()
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)

        from pipeline.extract import run
        result = run(provider="openai")

        assert result == 1
        mock_sb.table.return_value.update.assert_called_once()
        call_args = mock_sb.table.return_value.update.call_args[0][0]
        assert call_args["country_of_origin"] == "Guatemala"
        assert "char_count" in call_args
        assert "extracted_at" in call_args


class TestBackupRunUploadsToHuggingface:
    """backup.run() fetches all rows and uploads JSON to HF."""

    @patch("pipeline.backup.HfApi")
    @patch("pipeline.backup.fetch_all_asylum_cases")
    @patch("pipeline.backup.get_client")
    def test_uploads_snapshot(self, mock_get_client, mock_fetch_all, mock_hf_api_cls,
                               monkeypatch, tmp_path):
        monkeypatch.setenv("HF_TOKEN", "test-token")
        monkeypatch.setenv("HF_REPO", "testuser/test-repo")
        monkeypatch.setenv("BACKUP_SUMMARY_FILE", str(tmp_path / "backup_summary.txt"))

        fake_rows = [{"link": f"https://fake{i}.pdf", "country_of_origin": "Test"} for i in range(5)]
        mock_fetch_all.return_value = fake_rows
        mock_get_client.return_value = MagicMock()

        mock_api = MagicMock()
        mock_hf_api_cls.return_value = mock_api

        from pipeline.backup import run
        run()

        mock_api.create_repo.assert_called_once()
        mock_api.upload_file.assert_called_once()
        upload_kwargs = mock_api.upload_file.call_args[1]
        assert upload_kwargs["path_in_repo"] == "asylum_cases.json"
        assert upload_kwargs["repo_id"] == "testuser/test-repo"
        payload = json.loads(upload_kwargs["path_or_fileobj"])
        assert len(payload) == 5


class TestQaCheckRunProducesReport:
    """qa_check.run() samples cases and produces a report dict."""

    @patch("pipeline.qa_check.run_pipeline_health_checks")
    @patch("pipeline.qa_check.pymupdf")
    @patch("pipeline.qa_check.requests")
    @patch("pipeline.qa_check.get_client")
    def test_produces_valid_report(self, mock_get_client, mock_requests, mock_pymupdf,
                                    mock_health_checks):
        mock_sb = MagicMock()
        mock_get_client.return_value = mock_sb

        # Return 3 rows from Supabase
        rows = [
            {"link": f"https://fake{i}.pdf", "docket_no": f"25-{i}",
             "date_filed": "2026-01-01", "country_of_origin": "Guatemala",
             "country_of_origin_evidence": "From Guatemala.",
             "final_disposition": "Denied",
             "final_disposition_evidence": "Petition denied.",
             "asylum_requested": True,
             "asylum_requested_evidence": "Sought asylum.",
             "char_count": 5000}
            for i in range(3)
        ]
        mock_sb.table.return_value.select.return_value.not_.is_.return_value.execute.return_value.data = rows

        # Mock PDF download and text extraction
        mock_resp = MagicMock()
        mock_resp.content = b"fake-pdf"
        mock_requests.get.return_value = mock_resp

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Guatemala denied asylum 25-0 25-1 25-2 petition"
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        mock_pymupdf.open.return_value = mock_doc

        mock_health_checks.return_value = []

        from pipeline.qa_check import run
        report = run(sample_size=3)

        assert "cases" in report
        assert len(report["cases"]) == 3
        assert report["summary"]["passed"] + report["summary"]["failed"] + report["summary"]["errors"] == 3
