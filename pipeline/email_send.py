"""Send email via Gmail SMTP.

Replaces the previous SendGrid integration. Reads credentials from the
environment (same names used locally in .env and in GitHub Actions secrets):

    GMAIL_USER          — the sending Gmail address
    GMAIL_APP_PASSWORD  — a Gmail App Password (16 chars, not the account password)
    EMAIL_TO            — optional recipient override (defaults to VPalacios@USFCA.EDU)

Usage:
    from pipeline.email_send import send_email
    send_email("Subject", "<h3>hello</h3>", text="hello")
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
DEFAULT_TO = "VPalacios@USFCA.EDU"


def send_email(subject: str, html: str, *, text: str | None = None,
               to: str | None = None) -> bool:
    """Send an HTML email via Gmail SMTP.

    Returns True if sent, False if credentials are missing (logged, not raised)
    so a notification failure never takes down the calling pipeline.
    """
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = to or os.environ.get("EMAIL_TO") or DEFAULT_TO

    if not user or not password:
        print("GMAIL_USER / GMAIL_APP_PASSWORD not set — skipping email.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = recipient
    msg.set_content(text or "This message requires an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        print(f"Email sent to {recipient}.")
        return True
    except Exception as e:  # noqa: BLE001 — notification must never crash the pipeline
        print(f"WARNING: failed to send email: {e}")
        return False
