"""Shared fixtures for the Ninth Circuit test suite."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure project root is on sys.path so `pipeline.*` and `lib.*` imports work.
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ── Fake data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def fake_opinion():
    """A dict matching the shape returned by fetch.parse_rss."""
    return {
        "link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
        "case_title": "Doe v. Garland",
        "case_number": "25-5185",
        "date_filed": "2026-03-13",
        "published_status": "Published",
    }


@pytest.fixture
def fake_asylum_row():
    """A dict matching a fully-extracted asylum_cases row."""
    return {
        "link": "https://cdn.ca9.uscourts.gov/datastore/opinions/2026/03/13/25-5185.pdf",
        "docket_no": "25-5185",
        "date_filed": "2026-03-13",
        "published_status": "Published",
        "country_of_origin": "Guatemala",
        "country_of_origin_evidence": "Petitioner is a native of Guatemala.",
        "final_disposition": "Denied",
        "final_disposition_evidence": "The petition for review is denied.",
        "asylum_requested": True,
        "asylum_requested_evidence": "Petitioner sought asylum under 8 U.S.C. § 1158.",
        "withholding_requested": True,
        "withholding_requested_evidence": "Petitioner also sought withholding of removal.",
        "CAT_requested": False,
        "CAT_requested_evidence": "Not mentioned in the opinion.",
        "past_persecution_established": True,
        "past_persecution_established_evidence": "Petitioner testified to past persecution.",
        "credibility_credibility_finding": True,
        "credibility_credibility_finding_evidence": "The IJ found petitioner credible.",
        "country_conditions_cited": True,
        "country_conditions_cited_evidence": "Country conditions reports were cited.",
        "char_count": 12000,
        "extraction_model": "llama-3.3-70b-instruct",
    }


# ── Mock Supabase fixture ───────────────────────────────────────────────────

@pytest.fixture
def mock_supabase():
    """A MagicMock that simulates the Supabase client with chained calls."""
    client = MagicMock()

    # .table(name).upsert(...).execute()
    upsert_result = MagicMock()
    upsert_result.data = []
    client.table.return_value.upsert.return_value.execute.return_value = upsert_result

    # .table(name).update(...).eq(...).execute()
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    # .table(name).select(...).is_(...).order(...).limit(...).execute()
    select_chain = client.table.return_value.select.return_value
    select_chain.is_.return_value.order.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    select_chain.is_.return_value.execute.return_value = MagicMock(data=[])
    select_chain.not_.is_.return_value.execute.return_value = MagicMock(data=[])

    return client


@pytest.fixture
def env_provider(monkeypatch):
    """Set the env vars needed by classify_free / extract for OpenAI-compatible providers."""
    monkeypatch.setenv("PROVIDER_API_KEY", "test-key-123")
    monkeypatch.setenv("PROVIDER_BASE_URL", "https://test.api.example.com/v1")
    monkeypatch.setenv("MODEL", "test-model")
    monkeypatch.setenv("MODEL_LABEL", "test-model-label")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-key")
