"""Classify opinions using Gemini 2.0 Flash via Google AI Studio (free tier).

Uses the google-genai SDK with an API key instead of Vertex AI credentials.
Gemini can read PDFs directly by URL — no text extraction needed.

Free tier limits: 1,500 requests/day, 15 requests/minute.

Reads env vars:
  GOOGLE_AI_STUDIO_KEY  — API key from aistudio.google.com
  DATE_FROM             — classify opinions filed on/after this date (YYYY-MM-DD)
  DATE_TO               — classify opinions filed on/before this date (YYYY-MM-DD)
  CLASSIFY_LIMIT        — max opinions to classify (default: 1500)
  CLASSIFY_SUMMARY_FILE — path to write summary for email notification
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from google import genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from pipeline.classify_shared import CLASSIFICATION_PROMPT, insert_into_asylum_cases


MODEL = "gemini-2.0-flash"
MODEL_LABEL = "gemini-2.0-flash"


def classify_opinion(client: genai.Client, pdf_url: str) -> bool:
    """Send PDF URL to Gemini AI Studio and return True if asylum-related."""
    # Download PDF bytes and send inline (AI Studio doesn't fetch arbitrary URLs)
    resp = requests.get(pdf_url, timeout=30)
    resp.raise_for_status()
    pdf_part = types.Part.from_bytes(data=resp.content, mime_type="application/pdf")

    response = client.models.generate_content(
        model=MODEL,
        contents=[pdf_part, CLASSIFICATION_PROMPT],
    )

    raw = response.text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(raw)
    answer = result.get("answer", "").strip().lower()
    return answer == "yes"


def fetch_unclassified(supabase, limit: int, date_from: str, date_to: str) -> list[dict]:
    """Fetch unclassified opinions within the assigned date range."""
    return (
        supabase.table("all_opinions")
        .select("link, case_title, case_number, date_filed, published_status")
        .is_("asylum_related", "null")
        .gte("date_filed", date_from)
        .lte("date_filed", date_to)
        .order("date_filed")
        .limit(limit)
        .execute()
        .data
    )


def run() -> int:
    """Classify pending opinions in the assigned date range. Returns count classified."""
    api_key = os.environ.get("GOOGLE_AI_STUDIO_KEY")
    date_from = os.environ.get("DATE_FROM")
    date_to = os.environ.get("DATE_TO")
    limit = int(os.environ.get("CLASSIFY_LIMIT", "1500"))

    for var, name in [(api_key, "GOOGLE_AI_STUDIO_KEY"),
                      (date_from, "DATE_FROM"), (date_to, "DATE_TO")]:
        if not var:
            raise RuntimeError(f"{name} is not set.")

    client = genai.Client(api_key=api_key)
    supabase = get_client()

    pending = fetch_unclassified(supabase, limit, date_from, date_to)
    print(f"Found {len(pending)} unclassified opinions ({date_from} to {date_to})")

    classified = 0
    asylum_links = []

    for i, opinion in enumerate(pending):
        link = opinion["link"]
        print(f"[{i + 1}/{len(pending)}] {opinion.get('case_title', link)}")

        try:
            is_asylum = classify_opinion(client, link)
            now = datetime.now(timezone.utc).isoformat()

            supabase.table("all_opinions").update({
                "asylum_related": is_asylum,
                "classified_at": now,
                "classifying_model": MODEL_LABEL,
            }).eq("link", link).execute()

            if is_asylum:
                insert_into_asylum_cases(supabase, opinion)
                asylum_links.append(link)
                print(f"  -> asylum-related")
            else:
                print(f"  -> not asylum-related")

            classified += 1

        except json.JSONDecodeError as e:
            print(f"  ERROR: invalid JSON from model: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"Done. Classified {classified}/{len(pending)} opinions.")

    summary_file = os.environ.get("CLASSIFY_SUMMARY_FILE")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(f"Model: {MODEL_LABEL}\n")
            f.write(f"Range: {date_from} to {date_to}\n")
            f.write(f"Classified {classified}/{len(pending)} opinions\n")
            f.write(f"Asylum-related: {len(asylum_links)}\n")
            for link in asylum_links:
                f.write(f"  {link}\n")

    return classified


if __name__ == "__main__":
    run()
