"""One-off script to fix char_count for existing asylum cases in Supabase.

Downloads each PDF, extracts text with pymupdf, and updates the char_count column.
"""

import sys
from pathlib import Path

import pymupdf
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client


def main():
    supabase = get_client()

    result = supabase.table("asylum_cases").select("link, char_count").execute()
    rows = result.data

    print(f"Found {len(rows)} asylum cases")

    updated = 0
    for i, row in enumerate(rows):
        link = row["link"]
        print(f"[{i + 1}/{len(rows)}] {link}")

        try:
            resp = requests.get(link, timeout=120)
            resp.raise_for_status()

            doc = pymupdf.open(stream=resp.content, filetype="pdf")
            text = "".join(page.get_text() for page in doc)
            doc.close()

            new_count = len(text)
            old_count = row.get("char_count")

            supabase.table("asylum_cases").update(
                {"char_count": new_count}
            ).eq("link", link).execute()

            if old_count:
                print(f"  {old_count:,} -> {new_count:,} (was {old_count/new_count:.1f}x inflated)")
            else:
                print(f"  -> {new_count:,} chars")

            updated += 1

        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nUpdated {updated}/{len(rows)} cases")


if __name__ == "__main__":
    main()
