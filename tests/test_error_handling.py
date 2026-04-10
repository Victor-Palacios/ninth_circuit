"""Error handling tests — verify graceful recovery from failures."""

import json
from unittest.mock import MagicMock, patch


class TestClassifyFreeHandlesJsonDecodeError:
    """classify_free.run() continues past a JSONDecodeError from one opinion."""

    @patch("pipeline.classify_free.insert_into_asylum_cases")
    @patch("pipeline.classify_free.classify_opinion")
    @patch("pipeline.classify_free.fetch_unclassified")
    @patch("pipeline.classify_free.get_client")
    def test_continues_after_bad_json(self, mock_get_client, mock_fetch, mock_classify,
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

        # First call raises JSONDecodeError, second succeeds
        mock_classify.side_effect = [
            json.JSONDecodeError("bad json", "", 0),
            True,
        ]

        from pipeline.classify_free import run
        result = run()

        # Should have classified 1 (the second one succeeded)
        assert result == 1
        mock_insert.assert_called_once()


class TestClassifyFreeStopsOnRateLimit:
    """classify_free.run() breaks out of the loop on a 429 error."""

    @patch("pipeline.classify_free.insert_into_asylum_cases")
    @patch("pipeline.classify_free.classify_opinion")
    @patch("pipeline.classify_free.fetch_unclassified")
    @patch("pipeline.classify_free.get_client")
    def test_stops_on_429(self, mock_get_client, mock_fetch, mock_classify,
                           mock_insert, env_provider, tmp_path, monkeypatch):
        monkeypatch.setenv("CLASSIFY_SUMMARY_FILE", str(tmp_path / "summary.txt"))

        pending = [
            {"link": f"https://{i}.pdf", "case_title": f"Case {i}", "case_number": f"25-{i}",
             "date_filed": "2026-01-01", "published_status": "Published"}
            for i in range(3)
        ]
        mock_sb = MagicMock()
        mock_get_client.return_value = mock_sb
        mock_fetch.return_value = pending

        # First succeeds, second hits rate limit
        mock_classify.side_effect = [
            True,
            Exception("Error code: 429 — rate limited"),
        ]

        from pipeline.classify_free import run
        result = run()

        # Should have classified 1 then stopped (not crashed)
        assert result == 1
