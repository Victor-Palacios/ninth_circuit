"""Classify Ninth Circuit opinions as asylum-related or not using Gemini.

Reads unclassified rows from all_opinions (asylum_related IS NULL),
sends each PDF to Gemini 2.5 Pro for classification, and updates the
asylum_related boolean. Asylum cases are also inserted into asylum_cases.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from lib.gemini_client import send_pdf_to_gemini


from pipeline.classify_shared import CLASSIFICATION_PROMPT, insert_into_asylum_cases  # noqa: F401


def fetch_unclassified(supabase) -> list[dict]:
    """Fetch rows from all_opinions where asylum_related is NULL."""
    result = (
        supabase.table("all_opinions")
        .select("link, case_title, case_number, date_filed, published_status")
        .is_("asylum_related", "null")
        .execute()
    )
    return result.data


def classify_opinion(pdf_url: str) -> bool:
    """Send a PDF to Gemini and return True if asylum-related."""
    result = send_pdf_to_gemini(pdf_url, CLASSIFICATION_PROMPT)
    answer = result.get("answer", "").strip().lower()
    return answer == "yes"



def run(limit: int | None = None) -> int:
    """Classify pending opinions. Returns count classified."""
    supabase = get_client()
    pending = fetch_unclassified(supabase)

    if limit:
        pending = pending[:limit]

    print(f"Found {len(pending)} unclassified opinions")
    classified = 0

    for i, opinion in enumerate(pending):
        link = opinion["link"]
        print(f"[{i + 1}/{len(pending)}] Classifying: {opinion.get('case_title', link)}")

        try:
            is_asylum = classify_opinion(link)
            now = datetime.now(timezone.utc).isoformat()

            supabase.table("all_opinions").update({
                "asylum_related": is_asylum,
                "classified_at": now,
            }).eq("link", link).execute()

            if is_asylum:
                insert_into_asylum_cases(supabase, opinion)
                print(f"  -> asylum-related (inserted into asylum_cases)")
            else:
                print(f"  -> not asylum-related")

            classified += 1

        except json.JSONDecodeError as e:
            print(f"  ERROR: Gemini returned invalid JSON: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"Classified {classified} opinions")
    return classified


def main():
    parser = argparse.ArgumentParser(
        description="Classify Ninth Circuit opinions as asylum-related using Gemini"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of opinions to classify (default: all pending)",
    )
    args = parser.parse_args()
    run(limit=args.limit)


if __name__ == "__main__":
    main()
