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
from datetime import datetime, timedelta, timezone

import pymupdf
import requests
from google.cloud import storage
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from lib.supabase_client import get_client


GCS_BUCKET = "th-circuit-qa"
GCS_PREFIX = "qa_reports"
SAMPLE_SIZE = 10

# --- Extraction Quality: valid outcome vocabulary ---
VALID_DISPOSITIONS = {
    "granted", "denied", "remanded", "dismissed", "affirmed", "vacated",
    "granted in part", "denied in part", "remanded in part", "dismissed in part",
}

# --- Pipeline Health: thresholds ---
STALE_EXTRACTION_THRESHOLD = 50   # flag if more than this many cases are pending extraction
CLASSIFY_THROUGHPUT_HOURS = 24    # flag if no opinions were classified in this window

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
        # Only check for "asylum" in the PDF when the value is True
        # If False, absence of the word is expected and correct
        "get_keywords": lambda row: ["asylum"] if row.get("asylum_requested") is True else [],
    },
    {
        "field": "docket_no",
        "evidence": None,
        # The docket number should appear in the PDF
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


# Boolean fields that should always have evidence populated
BOOLEAN_FIELDS_WITH_EVIDENCE = [
    ("asylum_requested", "asylum_requested_evidence"),
    ("withholding_requested", "withholding_requested_evidence"),
    ("CAT_requested", "CAT_requested_evidence"),
    ("past_persecution_established", "past_persecution_established_evidence"),
    ("credibility_credibility_finding", "credibility_credibility_finding_evidence"),
    ("country_conditions_cited", "country_conditions_cited_evidence"),
]

CHAR_COUNT_MIN = 500       # below this likely a scanned/image PDF
CHAR_COUNT_MAX = 150_000   # above this suspiciously large
CHAR_COUNT_DRIFT_PCT = 15  # flag if DB char_count differs from live extraction by >15%


def check_case(row: dict, pdf_text: str) -> list[dict]:
    """Run all checks on a single case. Returns list of discrepancy dicts."""
    discrepancies = []
    text_lower = pdf_text.lower()

    # --- Existing keyword checks ---
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
                "check_type": "keyword_match",
            })

    # --- Evidence field completeness check ---
    # For True booleans: evidence must be non-empty and not the "not mentioned" placeholder
    # For False booleans: evidence must be "Not mentioned in the opinion." (or similar)
    for bool_field, evidence_field in BOOLEAN_FIELDS_WITH_EVIDENCE:
        value = row.get(bool_field)
        evidence = (row.get(evidence_field) or "").strip()

        if value is True and (not evidence or evidence.lower() == "not mentioned in the opinion."):
            discrepancies.append({
                "field": evidence_field,
                "db_value": evidence or None,
                "check_type": "missing_evidence",
                "detail": f"{bool_field} is True but evidence field is empty or says 'Not mentioned'.",
            })
        elif value is False and evidence and evidence.lower() not in (
            "not mentioned in the opinion.", "not mentioned.", "not addressed in the opinion."
        ):
            # False boolean should not have a substantive quote as evidence
            # (minor check — only flag if evidence looks like a real quote, i.e. long)
            if len(evidence) > 100:
                discrepancies.append({
                    "field": evidence_field,
                    "db_value": evidence[:100],
                    "check_type": "unexpected_evidence",
                    "detail": f"{bool_field} is False but evidence field contains substantive text — possible misclassification.",
                })

    # --- Char count plausibility check ---
    db_char_count = row.get("char_count")
    live_char_count = len(pdf_text)

    if db_char_count is not None:
        if db_char_count < CHAR_COUNT_MIN:
            discrepancies.append({
                "field": "char_count",
                "db_value": db_char_count,
                "check_type": "char_count_low",
                "detail": f"Only {db_char_count:,} characters extracted — PDF may be a scanned image with no readable text.",
            })
        elif db_char_count > CHAR_COUNT_MAX:
            discrepancies.append({
                "field": "char_count",
                "db_value": db_char_count,
                "check_type": "char_count_high",
                "detail": f"{db_char_count:,} characters is unusually large — possible extraction error.",
            })
        else:
            drift = abs(db_char_count - live_char_count) / max(live_char_count, 1) * 100
            if drift > CHAR_COUNT_DRIFT_PCT:
                discrepancies.append({
                    "field": "char_count",
                    "db_value": db_char_count,
                    "check_type": "char_count_drift",
                    "detail": f"DB char_count ({db_char_count:,}) differs from live extraction ({live_char_count:,}) by {drift:.1f}% — possible stale or incorrect value.",
                })

    return discrepancies


def run_pipeline_health_checks(supabase) -> list[dict]:
    """Run pipeline-level health checks. Returns list of issue dicts."""
    issues = []
    now = datetime.now(timezone.utc)

    # --- Extraction Quality: outcome vocabulary ---
    # Flag any final_disposition values outside the expected vocabulary
    all_dispositions = (
        supabase.table("asylum_cases")
        .select("docket_no,final_disposition")
        .not_.is_("final_disposition", "null")
        .execute()
    )
    bad_dispositions = []
    for row in all_dispositions.data:
        val = (row.get("final_disposition") or "").strip().lower()
        if not any(valid in val for valid in VALID_DISPOSITIONS):
            bad_dispositions.append({
                "docket_no": row.get("docket_no"),
                "final_disposition": row.get("final_disposition"),
            })
    if bad_dispositions:
        issues.append({
            "check": "outcome_vocabulary",
            "category": "Extraction Quality",
            "severity": "warning",
            "detail": f"{len(bad_dispositions)} case(s) have unexpected final_disposition values.",
            "examples": bad_dispositions[:5],
        })

    # --- Pipeline Health: stale extraction ---
    # Flag if too many asylum cases have never been through extraction (char_count IS NULL)
    # char_count is set during extraction, so it's the most reliable "extracted" indicator
    pending_extraction = (
        supabase.table("asylum_cases")
        .select("link", count="exact")
        .is_("char_count", "null")
        .execute()
    )
    pending_count = pending_extraction.count or 0
    if pending_count > STALE_EXTRACTION_THRESHOLD:
        issues.append({
            "check": "stale_extraction",
            "category": "Pipeline Health",
            "severity": "warning",
            "detail": f"{pending_count:,} asylum cases have never been extracted (char_count is null). The extract job may be paused or stuck.",
        })

    # --- Pipeline Health: daily fetch volume ---
    # Flag if no new opinions were fetched today
    today_str = now.strftime("%Y-%m-%d")
    todays_opinions = (
        supabase.table("all_opinions")
        .select("link", count="exact")
        .eq("date_filed", today_str)
        .execute()
    )
    todays_count = todays_opinions.count or 0
    if todays_count == 0:
        issues.append({
            "check": "fetch_volume",
            "category": "Pipeline Health",
            "severity": "warning",
            "detail": f"No opinions were fetched with today's date ({today_str}). The fetch job may have failed or the court published nothing today.",
        })
    else:
        issues.append({
            "check": "fetch_volume",
            "category": "Pipeline Health",
            "severity": "info",
            "detail": f"{todays_count} opinion(s) fetched with today's date ({today_str}).",
        })

    # --- Pipeline Health: classify throughput ---
    # Flag if no opinions were classified in the last 24 hours (and unclassified rows exist)
    cutoff = (now - timedelta(hours=CLASSIFY_THROUGHPUT_HOURS)).isoformat()
    recently_classified = (
        supabase.table("all_opinions")
        .select("link", count="exact")
        .not_.is_("classified_at", "null")
        .gte("classified_at", cutoff)
        .execute()
    )
    classified_count = recently_classified.count or 0

    unclassified = (
        supabase.table("all_opinions")
        .select("link", count="exact")
        .is_("asylum_related", "null")
        .execute()
    )
    unclassified_count = unclassified.count or 0

    if classified_count == 0 and unclassified_count > 0:
        issues.append({
            "check": "classify_throughput",
            "category": "Pipeline Health",
            "severity": "error",
            "detail": f"No opinions were classified in the last {CLASSIFY_THROUGHPUT_HOURS} hours, but {unclassified_count:,} unclassified rows remain. The classify job may be stuck or paused.",
        })
    else:
        issues.append({
            "check": "classify_throughput",
            "category": "Pipeline Health",
            "severity": "info",
            "detail": f"{classified_count:,} opinion(s) classified in the last {CLASSIFY_THROUGHPUT_HOURS} hours. {unclassified_count:,} still pending.",
        })

    return issues


def run(sample_size: int = SAMPLE_SIZE) -> dict:
    """Run QA check and return the full report dict."""
    supabase = get_client()

    columns = "link,docket_no,date_filed,country_of_origin,country_of_origin_evidence,final_disposition,final_disposition_evidence,asylum_requested,asylum_requested_evidence,char_count"
    result = (
        supabase.table("asylum_cases")
        .select(columns)
        .not_.is_("country_of_origin", "null")
        .execute()
    )

    all_rows = result.data
    sample = random.sample(all_rows, min(sample_size, len(all_rows)))

    # --- Pipeline Health checks (run once, not per-case) ---
    print("Running pipeline health checks...")
    pipeline_issues = run_pipeline_health_checks(supabase)
    pipeline_errors = [i for i in pipeline_issues if i["severity"] in ("error", "warning")]
    for issue in pipeline_issues:
        icon = "❌" if issue["severity"] == "error" else "⚠️" if issue["severity"] == "warning" else "ℹ️"
        print(f"  {icon} [{issue['check']}] {issue['detail']}")

    report = {
        "run_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_rows_in_db": len(all_rows),
        "sample_size": len(sample),
        "pipeline_health": pipeline_issues,
        "cases": [],
        "summary": {
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "pipeline_warnings": len(pipeline_errors),
        },
    }

    for row in sample:
        link = row["link"]
        case_result = {
            "docket_no": row.get("docket_no"),
            "country": row.get("country_of_origin", "—"),
            "disposition": row.get("final_disposition", "—"),
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
                detail = d.get("detail") or f"searched: {d.get('keywords_searched', '')}"
                print(f"         DISCREPANCY: {d['field']} = {d['db_value']!r} ({detail})")

    return report


FIELD_LABELS = {
    "country_of_origin": "Country of Origin",
    "final_disposition": "Final Outcome",
    "asylum_requested": "Asylum Requested",
    "docket_no": "Docket Number",
}


def _friendly_discrepancy(d: dict) -> str:
    field = FIELD_LABELS.get(d["field"], d["field"])
    db_val = d["db_value"]
    keywords = d.get("keywords_searched", [])

    if d["field"] == "asylum_requested":
        return (
            f"The database says asylum was <strong>{'requested' if db_val else 'not requested'}</strong>, "
            f"but the word \"asylum\" could not be confirmed in the PDF text. "
            f"This may be a scanned or image-based PDF where text extraction is limited."
        )
    if d["field"] == "final_disposition":
        return (
            f"The database records the final outcome as <strong>\"{db_val}\"</strong>, "
            f"but that exact phrasing wasn't found in the PDF. "
            f"The PDF may use slightly different wording (e.g. a comma instead of \"and\", or an abbreviated form). "
            f"Worth a quick manual check, but likely a false alarm."
        )
    if d["field"] == "country_of_origin":
        return (
            f"The database says the applicant is from <strong>{db_val}</strong>, "
            f"but that country name wasn't found in the PDF text. "
            f"This could indicate a data entry issue or a scanned PDF."
        )
    if d["field"] == "docket_no":
        return (
            f"The docket number <strong>{db_val}</strong> wasn't found in the PDF. "
            f"Some PDFs format docket numbers differently (e.g. with leading zeros or dashes)."
        )
    check_type = d.get("check_type", "")
    if check_type == "missing_evidence":
        return f"<strong>{d['field']}</strong>: {d.get('detail', 'Evidence field is empty despite a True value.')}"
    if check_type == "unexpected_evidence":
        return f"<strong>{d['field']}</strong>: {d.get('detail', 'Evidence field has content despite a False value.')}"
    if check_type in ("char_count_low", "char_count_high", "char_count_drift"):
        return f"<strong>Character Count</strong>: {d.get('detail', '')}"
    return f"Field <strong>{field}</strong> has value <strong>\"{db_val}\"</strong> in the database but could not be confirmed in the PDF."


def send_email(report: dict, gcs_uri: str):
    """Send a daily QA summary email via SendGrid."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        print("WARNING: SENDGRID_API_KEY not set, skipping email.")
        return

    s = report["summary"]
    date_str = report["run_date"][:10]
    all_passed = s["failed"] == 0 and s["errors"] == 0 and s["pipeline_warnings"] == 0
    status = "✅ All checks passed" if all_passed else f"⚠️ {s['failed'] + s['pipeline_warnings']} issue(s) found"

    body_lines = [
        f"<h2>Ninth Circuit QA Report — {date_str}</h2>",
        f"<p><strong>Status:</strong> {status}</p>",
        f"<p>Checked <strong>{report['sample_size']} randomly sampled cases</strong> "
        f"out of {report['total_rows_in_db']:,} total asylum cases in the database.</p>",
        f"<p><strong>Results:</strong> {s['passed']} passed &nbsp;|&nbsp; "
        f"{s['failed']} failed &nbsp;|&nbsp; {s['errors']} errors</p>",
        "<hr>",
        "<h3>What Was Checked</h3>",
        "<p>For each sampled case, the original PDF was downloaded and compared against the database record:</p>",
        "<ul>",
        "<li><strong>Country of Origin</strong> — Confirms the country name stored in the database appears in the PDF text.</li>",
        "<li><strong>Final Outcome</strong> — Confirms the outcome (e.g. Denied, Granted, Remanded) is supported by language in the PDF.</li>",
        "<li><strong>Asylum Requested</strong> — Confirms the word \"asylum\" appears in the PDF for cases marked as asylum-related.</li>",
        "<li><strong>Docket Number</strong> — Confirms the case docket number stored in the database is present in the PDF.</li>",
        "<li><strong>Evidence Completeness</strong> — For True boolean fields, confirms a supporting quote is present; for False fields, confirms no conflicting evidence exists.</li>",
        "<li><strong>Character Count</strong> — Confirms the stored character count is plausible and matches a fresh extraction from the PDF.</li>",
        "</ul>",
        "<h3>Pipeline Health Checks</h3>",
        "<ul>",
        "<li><strong>Outcome Vocabulary</strong> — Scans all asylum cases for final_disposition values outside the expected set (Granted, Denied, Remanded, etc.).</li>",
        "<li><strong>Stale Extraction</strong> — Flags if more than 50 asylum cases are still waiting for feature extraction.</li>",
        "<li><strong>Daily Fetch Volume</strong> — Confirms that new opinions were fetched from the court website today.</li>",
        "<li><strong>Classify Throughput</strong> — Confirms that opinions were classified in the last 24 hours while unclassified rows remain.</li>",
        "</ul>",
        "<h3>Pipeline Health</h3>",
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:sans-serif;font-size:13px;'>",
        "<tr style='background:#f0f0f0;'><th>Check</th><th>Status</th><th>Detail</th></tr>",
    ]

    for issue in report.get("pipeline_health", []):
        sev = issue["severity"]
        icon = "❌" if sev == "error" else "⚠️" if sev == "warning" else "✅"
        color = "#ffd6d6" if sev == "error" else "#fff3cd" if sev == "warning" else "#fff"
        examples = issue.get("examples", [])
        detail_text = issue["detail"]
        if examples:
            detail_text += " Examples: " + ", ".join(
                f"{e.get('docket_no')} ({e.get('final_disposition')})" for e in examples
            )
        body_lines.append(
            f"<tr style='background:{color};'>"
            f"<td>{issue['check'].replace('_', ' ').title()}</td>"
            f"<td>{icon}</td>"
            f"<td>{detail_text}</td>"
            f"</tr>"
        )

    body_lines += [
        "</table>",
        "<hr>",
        "<h3>All Checked Cases</h3>",
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;font-family:monospace;'>",
        "<tr style='background:#f0f0f0;'><th>#</th><th>Docket</th><th>Country</th><th>Outcome</th><th>Result</th></tr>",
    ]

    for i, c in enumerate(report["cases"], 1):
        color = "#fff" if c["status"] == "PASS" else "#fff3cd" if c["status"] == "FAIL" else "#ffd6d6"
        icon = "✅" if c["status"] == "PASS" else "⚠️" if c["status"] == "FAIL" else "❌"
        # Pull country/outcome from discrepancy data or from the report cases
        body_lines.append(
            f"<tr style='background:{color};'>"
            f"<td>{i}</td>"
            f"<td>{c.get('docket_no', '—')}</td>"
            f"<td>{c.get('country', '—')}</td>"
            f"<td>{c.get('disposition', '—')}</td>"
            f"<td>{icon} {c['status']}</td>"
            f"</tr>"
        )

    body_lines.append("</table>")

    failures = [c for c in report["cases"] if c["status"] in ("FAIL", "ERROR")]
    if failures:
        body_lines.append("<hr><h3>Issues Requiring Attention</h3>")
        for c in failures:
            body_lines.append(f"<h4>Case {c.get('docket_no', 'Unknown')} — {c['status']}</h4><ul>")
            for d in c.get("discrepancies", []):
                body_lines.append(f"<li>{_friendly_discrepancy(d)}</li>")
            if c.get("error"):
                body_lines.append(f"<li>⚠️ Could not download or read the PDF: {c['error']}</li>")
            body_lines.append("</ul>")
    else:
        body_lines.append("<hr><p>No issues found. All sampled cases passed data integrity checks.</p>")

    body_lines.append(f"<hr><p style='color:#888;font-size:12px;'>Full JSON report: {gcs_uri}</p>")

    message = Mail(
        from_email="VPalacios@USFCA.EDU",
        to_emails="VPalacios@USFCA.EDU",
        subject=f"Ninth Circuit QA — {date_str} — {status}",
        html_content="\n".join(body_lines),
    )

    try:
        sg = SendGridAPIClient(api_key)
        sg.send(message)
        print("QA report email sent to VPalacios@USFCA.EDU")
    except Exception as e:
        print(f"WARNING: Failed to send email: {e}")


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

    gcs_uri = upload_report(report)
    send_email(report, gcs_uri)

    if s["failed"] > 0 or s["errors"] > 0:
        print("\nWARNING: Discrepancies found — review report in GCS.")
