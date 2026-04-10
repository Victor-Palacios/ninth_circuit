"""Data validation tests — verify QA checks catch data quality issues."""

from pipeline.qa_check import check_case


class TestCheckCaseDetectsMissingEvidence:
    """Flags when a True boolean has placeholder evidence."""

    def test_true_boolean_with_not_mentioned_evidence(self):
        row = {
            "country_of_origin": "Guatemala",
            "country_of_origin_evidence": "From Guatemala.",
            "final_disposition": "Denied",
            "final_disposition_evidence": "Petition denied.",
            "asylum_requested": True,
            "asylum_requested_evidence": "Not mentioned in the opinion.",  # BUG: True but placeholder
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
            "char_count": 8000,
        }
        pdf_text = "Guatemala asylum denied 25-5185 petition"

        discrepancies = check_case(row, pdf_text)
        missing = [d for d in discrepancies if d["check_type"] == "missing_evidence"]
        assert len(missing) >= 1
        assert any("asylum_requested" in d.get("detail", "") for d in missing)


class TestCheckCaseDetectsCharCountTooLow:
    """Flags suspiciously low char_count values."""

    def test_char_count_below_threshold(self):
        row = {
            "country_of_origin": "Test",
            "country_of_origin_evidence": "From Test.",
            "final_disposition": "Denied",
            "final_disposition_evidence": "Denied.",
            "asylum_requested": False,
            "asylum_requested_evidence": "Not mentioned in the opinion.",
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
            "docket_no": "25-1",
            "char_count": 50,  # way below the 500 threshold
        }
        pdf_text = "Test denied 25-1"

        discrepancies = check_case(row, pdf_text)
        low_count = [d for d in discrepancies if d["check_type"] == "char_count_low"]
        assert len(low_count) == 1
        assert "50" in low_count[0]["detail"]
