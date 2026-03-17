"""Classify opinions as asylum-related using DeepSeek via OpenRouter.

Uses the OpenAI-compatible OpenRouter API. Since OpenRouter cannot fetch
PDFs by URL, each PDF is downloaded and text is extracted with pymupdf
before being sent to the model.

Reads env vars:
  OPENROUTER_API_KEY  — OpenRouter API key
  CLASSIFY_LIMIT      — max opinions to classify (default 10)

Usage (local):
  OPENROUTER_API_KEY=... python -m pipeline.classify_openrouter

This is the daily classifier. The regular classify.py (Gemini) is used
for bulk backfill only.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import fitz  # pymupdf
import requests
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from pipeline.classify import CLASSIFICATION_PROMPT, insert_into_asylum_cases


# OpenRouter model — DeepSeek V3 free tier
MODEL = "deepseek/deepseek-chat-v3-0324:free"
MODEL_LABEL = "deepseek-chat-v3-0324"

# Truncate PDF text to keep token usage low (classification only needs key context)
MAX_TEXT_CHARS = 6000


def extract_text_from_pdf(pdf_url: str) -> str:
    """Download a PDF and extract its text content."""
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return text[:MAX_TEXT_CHARS]


def classify_opinion(client: OpenAI, pdf_url: str) -> bool:
    """Extract text from PDF and classify via DeepSeek. Returns True if asylum-related."""
    text = extract_text_from_pdf(pdf_url)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": f"{CLASSIFICATION_PROMPT}\n\nOpinion text:\n{text}",
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)
    answer = result.get("answer", "").strip().lower()
    return answer == "yes"


def fetch_unclassified(supabase, limit: int) -> list[dict]:
    """Fetch unclassified opinions ordered by date (most recent first)."""
    result = (
        supabase.table("all_opinions")
        .select("link, case_title, case_number, date_filed, published_status")
        .is_("asylum_related", "null")
        .order("date_filed", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


def run(limit: int = 10) -> int:
    """Classify pending opinions. Returns count classified."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set.")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    supabase = get_client()
    pending = fetch_unclassified(supabase, limit)
    print(f"Found {len(pending)} unclassified opinions (limit={limit})")

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

    # Write summary for GitHub Actions email notification
    summary_file = os.environ.get("CLASSIFY_SUMMARY_FILE")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(f"Classified {classified}/{len(pending)} opinions\n")
            f.write(f"Asylum-related: {len(asylum_links)}\n")
            for link in asylum_links:
                f.write(f"  {link}\n")

    return classified


def main():
    limit = int(os.environ.get("CLASSIFY_LIMIT", "10"))
    run(limit=limit)


if __name__ == "__main__":
    main()
