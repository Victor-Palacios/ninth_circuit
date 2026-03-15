"""Daily QA check for asylum_cases data integrity.

Samples 10 random asylum cases, downloads each PDF, and verifies that
key extracted fields are consistent with the PDF text. Writes a JSON
report to GCS at gs://th-circuit-qa/qa_reports/YYYY-MM-DD.json.

The check uses smart matching (keyword presence) rather than exact
string matching to avoid false negatives from whitespace/formatting.
"""

import json
import os
import random
import re
from datetime import datetime

import pymupdf
import requests
from google.cloud import storage

from lib.supabase_client import get_client


GCS_BUCKET = "th-circuit-qa"
GCS_PREFIX = "qa_reports"
SAMPLE_SIZE = 10

# For each field: (db_column, evidence_column, keywords_fn)
# keywords_fn(row) returns a list of strings that should appear in the PDF
CHECKS = [
    {
        "field": "country_of_origin",
        "evidence": "country_of_origin_evidence",
        # The country name itself should appear somewhere in the PDF
        "get_keywords": lambda row: [row["country_of_origin"]] if row.get("country_of_origin") else [],
    },
    {
        "field": "final_disposition",
        "evidence": "final_disposition_evidence",
        # Key disposition words should appear in the PDF
        "get_keywords": lambda row: _disposition_keywords(row.get("final_disposition")),
    },
    {
        "field": "asylum_requested",
        "evidence": "asylum_requested_evidence",
        # The word "asylum" should always appear in an asylum case
        "get_keywords": lambda row: ["asylum"] if row.get("asylum_requested") is not None else [],
    },
    {
        "field": "docket_no",
        "evidence": None,
        # The docket number (without leading zeros) should appear in the PDF
        "get_keywords": lambda row: _docket_keywords(row.get("docket_no")),
    },
]

DISPOSITION_MAP = {
    "Denied": ["denied", "petition for review is denied", "petition is denied"],
    "Granted": ["granted", "petition for review is granted", "remand"],
    "Remanded": ["remanded", "remand"],
    "Dismissed": ["dismissed"],
    "Affirmed": ["affirmed", "affirm"],
    "Vacated": ["vacated", "vacate"],
}


def _disposition_keywords(disposition: str | None) -> list[str]:
    if not disposition:
        return []
    return DISPOSITION_MAP.get(disposition, [disposition.lower()])


def _docket_keywords(docket: str | None) -> list[str]:
    if not docket:
        return []
    # Normalize: remove leading zeros from the number part (e.g. 20-73521 → 20-73521)
    # Also try without the leading zero variant: 20-73521 and 20-073521 both appear in PDFs
    variants = [docket]
    # Try stripping leading zeros after the dash
    parts = docket.split("-")
    if len(parts) == 2:
        try:
            variants.append(f"{parts[0]}-{int(parts[1])}")
        except ValueError:
            pass
    return variants


def check_case(row: dict, pdf_text: str) -> list[dict]:
    """Run all checks on a single case. Returns list of discrepancy dicts."""
    discrepancies = []
    text_lower = pdf_text.lower()

    for check in CHECKS:
        field = check["field"]
        keywords = check["get_keywords"](row)

        if not keywords:
            continue

        found = any(kw.lower() in text_lower for kw in keywords)
        if not found:
            discrepancies.append({
                "field": field,
                "db_value": row.get(field),
                "keywords_searched": keywords,
                "evidence_snippet": (row.get(check["evidence"]) or "")[:200] if check["evidence"] else None,
            })

    return discrepancies


def run(sample_size: int = SAMPLE_SIZE) -> dict:
    """Run QA check and return the full report dict."""
    supabase = get_client()

    columns = "link,docket_no,date_filed,country_of_origin,country_of_origin_evidence,final_disposition,final_disposition_evidence,asylum_requested,asylum_requested_evidence"
    result = (
        supabase.table("asylum_cases")
        .select(columns)
        .not_.is_("country_of_origin", "null")
        .execute()
    )

    all_rows = result.data
    sample = random.sample(all_rows, min(sample_size, len(all_rows)))

    report = {
        "run_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_rows_in_db": len(all_rows),
        "sample_size": len(sample),
        "cases": [],
        "summary": {
            "passed": 0,
            "failed": 0,
            "errors": 0,
        },
    }

    for row in sample:
        link = row["link"]
        case_result = {
            "docket_no": row.get("docket_no"),
            "link": link,
            "status": None,
            "discrepancies": [],
            "error": None,
        }

        try:
            resp = requests.get(link, timeout=60)
            resp.raise_for_status()
            doc = pymupdf.open(stream=resp.content, filetype="pdf")
            pdf_text = "".join(page.get_text() for page in doc)
            doc.close()

            discrepancies = check_case(row, pdf_text)
            case_result["discrepancies"] = discrepancies
            case_result["status"] = "FAIL" if discrepancies else "PASS"

            if discrepancies:
                report["summary"]["failed"] += 1
            else:
                report["summary"]["passed"] += 1

        except Exception as e:
            case_result["status"] = "ERROR"
            case_result["error"] = str(e)
            report["summary"]["errors"] += 1

        report["cases"].append(case_result)
        status = case_result["status"]
        print(f"  [{status}] {row.get('docket_no')} — {row.get('country_of_origin')} / {row.get('final_disposition')}")
        if case_result["discrepancies"]:
            for d in case_result["discrepancies"]:
                print(f"         DISCREPANCY: {d['field']} = {d['db_value']!r} (searched: {d['keywords_searched']})")

    return report


def upload_report(report: dict) -> str:
    """Upload the report JSON to GCS. Returns the GCS URI."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    blob_name = f"{GCS_PREFIX}/{date_str}.json"

    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(report, indent=2),
        content_type="application/json",
    )
    uri = f"gs://{GCS_BUCKET}/{blob_name}"
    print(f"\nReport uploaded to {uri}")
    return uri


def main():
    print("=" * 60)
    print("Ninth Circuit QA Check")
    print("=" * 60)

    report = run()

    s = report["summary"]
    print(f"\nSummary: {s['passed']} passed, {s['failed']} failed, {s['errors']} errors")

    upload_report(report)

    if s["failed"] > 0 or s["errors"] > 0:
        print("\nWARNING: Discrepancies found — review report in GCS.")
