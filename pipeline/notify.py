"""Send a SendGrid email notification after a pipeline run.

Usage: python pipeline/notify.py <subject_label>
  subject_label: human-readable provider label, e.g. "HuggingFace (Llama 2020)"

Reads env vars:
  JOB_STATUS        — success or failure
  RUN_URL           — GitHub Actions run URL
  SENDGRID_API_KEY  — SendGrid API key
  JOB_TYPE          — prefix for subject line (default: "Classify")
  SUMMARY_FILE      — path to summary file (default: classify_summary.txt)
"""

import os
import sys

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

subject_label = sys.argv[1]
status = os.environ["JOB_STATUS"]
run_url = os.environ["RUN_URL"]
job_type = os.environ.get("JOB_TYPE", "Classify")
icon = "✅" if status == "success" else "❌"

summary_file = os.environ.get("SUMMARY_FILE",
                              os.environ.get("CLASSIFY_SUMMARY_FILE", "classify_summary.txt"))
summary, asylum_links = "", []
try:
    for line in open(summary_file).read().strip().splitlines():
        if line.strip().startswith("http"):
            asylum_links.append(line.strip())
        else:
            summary += line + "\n"
except FileNotFoundError:
    summary = "No summary available."

links_html = (
    "<ul>" + "".join(f"<li><a href='{l}'>{l}</a></li>" for l in asylum_links) + "</ul>"
    if asylum_links
    else "<p>None found.</p>"
)

sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
sg.send(Mail(
    from_email="VPalacios@USFCA.EDU",
    to_emails="VPalacios@USFCA.EDU",
    subject=f"{icon} {job_type} {subject_label} — {status}",
    html_content=(
        f"<h3>{icon} {status}</h3>"
        f"<pre>{summary}</pre>"
        f"<h4>Asylum cases ({len(asylum_links)}):</h4>{links_html}"
        f"<p><a href='{run_url}'>View logs</a></p>"
    ),
))
print("Email sent.")
