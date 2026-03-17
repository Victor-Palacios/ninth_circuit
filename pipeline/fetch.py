"""Fetch new Ninth Circuit opinions from ca9.uscourts.gov.

Data sources:
  - RSS: /opinions/index.xml (published) and /memoranda/index.xml (unpublished)
  - HTML: scrape search pages for full metadata (case origin, judge, type)

The RSS feeds provide case title, PDF link, and date filed.
Additional metadata is scraped from the HTML search pages.
"""

import argparse
import os
import re
import time
from datetime import datetime
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

# Add project root to path for lib imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client


# ── Constants ────────────────────────────────────────────────────────────────

RSS_OPINIONS = "https://www.ca9.uscourts.gov/opinions/index.xml"
RSS_MEMORANDA = "https://www.ca9.uscourts.gov/memoranda/index.xml"

SEARCH_OPINIONS = "https://www.ca9.uscourts.gov/opinions/"
SEARCH_MEMORANDA = "https://www.ca9.uscourts.gov/memoranda/"

TABLE = "all_opinions"
SCRAPE_DELAY = 1.5  # seconds between HTML requests (polite crawling)


# ── RSS Parsing ──────────────────────────────────────────────────────────────

def parse_rss(feed_url: str, published_status: str) -> list[dict]:
    """Parse an RSS feed and return a list of opinion dicts."""
    feed = feedparser.parse(feed_url)
    opinions = []

    for entry in feed.entries:
        link = entry.get("link", "").strip()
        if not link:
            continue

        title = entry.get("title", "").strip()

        # Extract case number from PDF URL: .../25-5185.pdf → 25-5185
        case_number = _extract_case_number_from_url(link)

        # Parse date from description: "Date Filed 03/13/2026"
        date_filed = _parse_date_from_description(entry.get("description", ""))

        opinions.append({
            "link": link,
            "case_title": title,
            "case_number": case_number,
            "date_filed": date_filed,
            "published_status": published_status,
        })

    return opinions


def _extract_case_number_from_url(url: str) -> str | None:
    """Extract case number from PDF URL like .../25-5185.pdf."""
    match = re.search(r"/([\d]+-[\d]+)\.pdf", url)
    return match.group(1) if match else None


def _parse_date_from_description(desc: str) -> str | None:
    """Parse 'Date Filed MM/DD/YYYY' into 'YYYY-MM-DD'."""
    match = re.search(r"(\d{2}/\d{2}/\d{4})", desc)
    if match:
        try:
            dt = datetime.strptime(match.group(1), "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


# ── HTML Scraping ────────────────────────────────────────────────────────────

def scrape_metadata_for_case(
    case_number: str,
    search_url: str,
) -> dict:
    """Scrape the ca9 search page for additional metadata about a case.

    Returns dict with: case_origin, authoring_judge, case_type.
    """
    try:
        params = {"title": case_number}
        resp = requests.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Warning: could not scrape metadata for {case_number}: {e}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find table rows — the search results are in an HTML table
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        # Check if this row matches our case number
        row_case_no = cells[1].get_text(strip=True)
        if case_number and case_number in row_case_no:
            return {
                "case_origin": cells[2].get_text(strip=True) or None,
                "authoring_judge": cells[3].get_text(strip=True) or None,
                "case_type": cells[4].get_text(strip=True) or None,
            }

    return {}


# ── Database ─────────────────────────────────────────────────────────────────


def insert_opinions(supabase, opinions: list[dict]) -> int:
    """Insert new opinions into all_opinions. Returns count inserted.

    Uses insert with ignore_duplicates=True (ON CONFLICT DO NOTHING) so
    any duplicate links are silently skipped rather than crashing.
    """
    if not opinions:
        return 0
    result = (
        supabase.table(TABLE)
        .upsert(opinions, ignore_duplicates=True)
        .execute()
    )
    return len(result.data)


# ── Main ─────────────────────────────────────────────────────────────────────

def fetch_today(scrape_html: bool = True) -> int:
    """Fetch new opinions from RSS feeds and insert into all_opinions.

    Returns the number of new opinions inserted.
    """
    supabase = get_client()

    # Parse both RSS feeds and deduplicate by link
    published = parse_rss(RSS_OPINIONS, "Published")
    unpublished = parse_rss(RSS_MEMORANDA, "Unpublished")
    seen = {}
    for e in published + unpublished:
        seen[e["link"]] = e
    all_entries = list(seen.values())
    print(f"RSS: {len(all_entries)} opinions fetched")

    # Optionally scrape HTML for additional metadata
    if scrape_html:
        for entry in all_entries:
            case_no = entry.get("case_number")
            if not case_no:
                continue

            search_url = (
                SEARCH_OPINIONS
                if entry["published_status"] == "Published"
                else SEARCH_MEMORANDA
            )
            extra = scrape_metadata_for_case(case_no, search_url)
            entry.update(extra)
            time.sleep(SCRAPE_DELAY)

    count = insert_opinions(supabase, all_entries)
    print(f"Inserted {count} new opinions")

    # Write summary for GitHub Actions email notification
    summary_file = os.environ.get("FETCH_SUMMARY_FILE")
    if summary_file:
        with open(summary_file, "w") as f:
            f.write(f"RSS: {len(all_entries)} opinions fetched\n")
            f.write(f"Inserted {count} new opinions into all_opinions\n")

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Fetch new Ninth Circuit opinions from ca9.uscourts.gov"
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip HTML scraping for additional metadata (faster, less data)",
    )
    args = parser.parse_args()
    fetch_today(scrape_html=not args.no_scrape)


if __name__ == "__main__":
    main()
