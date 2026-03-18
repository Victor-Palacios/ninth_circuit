"""Generic classifier for OpenAI-compatible free-tier providers.

Handles OpenRouter, Groq, GitHub Models, and HuggingFace Inference API.
All config is passed via env vars so the same script runs for all four
providers — only the workflow changes the values.

Reads env vars:
  PROVIDER_API_KEY    — API key for the provider
  PROVIDER_BASE_URL   — OpenAI-compatible base URL
  MODEL               — model name to use in API call
  MODEL_LABEL         — value stored in classifying_model column
  DATE_FROM           — classify opinions filed on/after this date (YYYY-MM-DD)
  DATE_TO             — classify opinions filed on/before this date (YYYY-MM-DD)
  CLASSIFY_LIMIT      — max opinions to classify (default: 500)
  CLASSIFY_SUMMARY_FILE — path to write summary for email notification

Provider config reference:
  OpenRouter:     base_url=https://openrouter.ai/api/v1
  Groq:           base_url=https://api.groq.com/openai/v1
  GitHub Models:  base_url=https://models.inference.ai.azure.com
  HuggingFace:    base_url=https://api-inference.huggingface.co/v1/
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
from pipeline.classify_shared import CLASSIFICATION_PROMPT, insert_into_asylum_cases


MAX_TEXT_CHARS = 6000


def extract_text_from_pdf(pdf_url: str) -> str:
    """Download a PDF and extract its text content."""
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    doc = fitz.open(stream=response.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    return text[:MAX_TEXT_CHARS]


def classify_opinion(client: OpenAI, model: str, pdf_url: str) -> bool:
    """Extract PDF text and classify via the provider. Returns True if asylum-related."""
    text = extract_text_from_pdf(pdf_url)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": f"{CLASSIFICATION_PROMPT}\n\nOpinion text:\n{text}",
            }
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    result = json.loads(raw)
    answer = result.get("answer", "").strip().lower()
    return answer == "yes"


def fetch_unclassified(supabase, limit: int, date_from: str, date_to: str) -> list[dict]:
    """Fetch unclassified opinions within the assigned date range."""
    query = (
        supabase.table("all_opinions")
        .select("link, case_title, case_number, date_filed, published_status")
        .is_("asylum_related", "null")
        .gte("date_filed", date_from)
        .lte("date_filed", date_to)
        .order("date_filed", desc=True)
        .limit(limit)
    )
    return query.execute().data


def run() -> int:
    """Classify pending opinions in the assigned date range. Returns count classified."""
    api_key = os.environ.get("PROVIDER_API_KEY")
    base_url = os.environ.get("PROVIDER_BASE_URL")
    model = os.environ.get("MODEL")
    model_label = os.environ.get("MODEL_LABEL")
    date_from = os.environ.get("DATE_FROM")
    date_to = os.environ.get("DATE_TO")
    limit = int(os.environ.get("CLASSIFY_LIMIT", "500"))

    for var, name in [(api_key, "PROVIDER_API_KEY"), (base_url, "PROVIDER_BASE_URL"),
                      (model, "MODEL"), (model_label, "MODEL_LABEL"),
                      (date_from, "DATE_FROM"), (date_to, "DATE_TO")]:
        if not var:
            raise RuntimeError(f"{name} is not set.")

    client = OpenAI(base_url=base_url, api_key=api_key)
    supabase = get_client()

    pending = fetch_unclassified(supabase, limit, date_from, date_to)
    print(f"Found {len(pending)} unclassified opinions ({date_from} to {date_to})")

    classified = 0
    asylum_links = []

    for i, opinion in enumerate(pending):
        link = opinion["link"]
        print(f"[{i + 1}/{len(pending)}] {opinion.get('case_title', link)}")

        try:
            is_asylum = classify_opinion(client, model, link)
            now = datetime.now(timezone.utc).isoformat()

            supabase.table("all_opinions").update({
                "asylum_related": is_asylum,
                "classified_at": now,
                "classifying_model": model_label,
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
            if "Error code: 429" in str(e) or "Error code: 402" in str(e):
                print("  Rate limit or quota exhausted — stopping early.")
                break

    print(f"Done. Classified {classified}/{len(pending)} opinions.")

    summary_file = os.environ.get("CLASSIFY_SUMMARY_FILE")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(f"Model: {model_label}\n")
            f.write(f"Range: {date_from} to {date_to}\n")
            f.write(f"Classified {classified}/{len(pending)} opinions\n")
            f.write(f"Asylum-related: {len(asylum_links)}\n")
            for link in asylum_links:
                f.write(f"  {link}\n")

    return classified


if __name__ == "__main__":
    run()
