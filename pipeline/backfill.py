"""Backfill historical opinions from ca9.uscourts.gov search pages.

Scrapes the opinions and memoranda search pages for a date range,
inserts into all_opinions, then runs classification and extraction.

Usage:
    python -m pipeline.backfill --start-date 2023-01-01 --end-date 2023-03-31
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from pipeline import classify, extract


SEARCH_OPINIONS = "https://www.ca9.uscourts.gov/opinions/"
SEARCH_MEMORANDA = "https://www.ca9.uscourts.gov/memoranda/"

TABLE = "all_opinions"
SCRAPE_DELAY = 1.5


def scrape_search_page(
    search_url: str,
    start_date: str,
    end_date: str,
    published_status: str,
) -> list[dict]:
    """Scrape a ca9 search page for opinions in a date range.

    Args:
        search_url: Base URL for the search page
        start_date: Start date in MM/DD/YYYY format
        end_date: End date in MM/DD/YYYY format
        published_status: "Published" or "Unpublished"

    Returns:
        List of opinion dicts ready for insertion.
    """
    opinions = []
    params = {
        "fromDate": start_date,
        "toDate": end_date,
    }

    try:
        resp = requests.get(search_url, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {search_url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        # Extract PDF link from first cell
        link_tag = cells[0].find("a", href=True)
        if not link_tag:
            continue
        link = link_tag["href"]
        if not link.startswith("http"):
            link = "https://cdn.ca9.uscourts.gov" + link

        case_title = cells[0].get_text(strip=True)
        case_number = cells[1].get_text(strip=True) or None
        case_origin = cells[2].get_text(strip=True) or None
        authoring_judge = cells[3].get_text(strip=True) or None
        case_type = cells[4].get_text(strip=True) or None
        date_text = cells[5].get_text(strip=True)

        # Parse date MM/DD/YYYY → YYYY-MM-DD
        date_filed = None
        try:
            dt = datetime.strptime(date_text, "%m/%d/%Y")
            date_filed = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass

        opinions.append({
            "link": link,
            "case_title": case_title,
            "case_number": case_number,
            "case_origin": case_origin,
            "authoring_judge": authoring_judge,
            "case_type": case_type,
            "date_filed": date_filed,
            "published_status": published_status,
        })

    return opinions


def backfill(
    start_date: str,
    end_date: str,
    classify_after: bool = True,
    extract_after: bool = True,
    month_chunk: bool = True,
):
    """Backfill opinions for a date range.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        classify_after: Run classification after inserting
        extract_after: Run extraction after classifying
        month_chunk: Process one month at a time (resume-friendly)
    """
    supabase = get_client()

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # Process in monthly chunks for resume-friendliness
    current = start
    total_inserted = 0

    while current < end:
        if month_chunk:
            chunk_end = min(
                current.replace(day=28) + timedelta(days=4),  # next month
                end,
            )
            chunk_end = chunk_end.replace(day=1) - timedelta(days=1)  # last day of month
            chunk_end = min(chunk_end, end)
        else:
            chunk_end = end

        from_str = current.strftime("%m/%d/%Y")
        to_str = chunk_end.strftime("%m/%d/%Y")
        print(f"\n--- Backfilling {current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} ---")

        # Scrape both published and unpublished
        published = scrape_search_page(SEARCH_OPINIONS, from_str, to_str, "Published")
        time.sleep(SCRAPE_DELAY)
        unpublished = scrape_search_page(SEARCH_MEMORANDA, from_str, to_str, "Unpublished")
        time.sleep(SCRAPE_DELAY)

        all_entries = published + unpublished
        print(f"  Found {len(published)} published + {len(unpublished)} unpublished")

        if all_entries:
            try:
                result = supabase.table(TABLE).upsert(
                    all_entries, on_conflict="link"
                ).execute()
                inserted = len(result.data)
                total_inserted += inserted
                print(f"  Inserted/updated {inserted} rows")
            except Exception as e:
                print(f"  ERROR inserting: {e}")
                if "storage" in str(e).lower() or "quota" in str(e).lower():
                    print("  Supabase storage limit likely reached. Stopping.")
                    break

        # Move to next month
        current = chunk_end + timedelta(days=1)

    print(f"\nBackfill complete. Total rows inserted/updated: {total_inserted}")

    # Run classification and extraction on the new data
    if classify_after:
        print("\n--- Running classification ---")
        classify.run()

    if extract_after:
        print("\n--- Running extraction ---")
        extract.run()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical opinions from ca9.uscourts.gov"
    )
    parser.add_argument(
        "--start-date",
        default="2023-01-01",
        help="Start date YYYY-MM-DD (default: 2023-01-01)",
    )
    parser.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--no-classify",
        action="store_true",
        help="Skip classification after backfill",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip extraction after backfill",
    )
    args = parser.parse_args()

    backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        classify_after=not args.no_classify,
        extract_after=not args.no_extract,
    )


if __name__ == "__main__":
    main()
