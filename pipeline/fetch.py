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
        .upsert(opinions, ignore_duplicates=True, on_conflict="link")
        .execute()
    )
    return len(result.data)


# ── Selenium Crawl + GCS Upload (Author: Diane Woodbridge) ───────────────────

def _safe_filename(s: str) -> str:
    """Replace characters illegal in filenames with dashes.

    Author: Diane Woodbridge
    """
    return re.sub(r'[/\\:*?"<>|]', '-', s)


def upload_to_gcs(gcs_client, bucket_name: str, blob_name: str, pdf_url: str) -> None:
    """Download a PDF from pdf_url and upload it to GCS.

    Skips silently if the blob already exists in the bucket.

    Author: Diane Woodbridge
    """
    bucket = gcs_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    if blob.exists():
        print(f"  Skipping (exists): gs://{bucket_name}/{blob_name}")
        return
    try:
        r = requests.get(pdf_url, timeout=30)
        r.raise_for_status()
        blob.upload_from_string(r.content, content_type="application/pdf")
        print(f"  Uploaded: gs://{bucket_name}/{blob_name}")
    except Exception as e:
        print(f"  FAILED {pdf_url}: {e}")


def expand_all_pages(driver, years: list) -> None:
    """Click the 'next page' button until no more pages or dates go outside target years.

    Author: Diane Woodbridge
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    min_year = min(years)
    page = 1
    while True:
        try:
            btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//span[contains(@onclick, \"dynamodbSearch\") and contains(@onclick, 'staticMore')]"
                ))
            )
        except Exception:
            print(f"  No more pages after {page} click(s). Table fully loaded.")
            break

        before = driver.execute_script(
            "return document.querySelectorAll('table tbody tr').length"
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        btn.click()
        print(f"  Clicked page {page}, waiting for new rows...")

        try:
            WebDriverWait(driver, 15).until(
                lambda d: d.execute_script(
                    "return document.querySelectorAll('table tbody tr').length"
                ) > before
            )
        except Exception:
            print("  Timed out waiting for new rows — stopping expansion.")
            break

        # Find minimum valid year (19xx/20xx) in the date column
        oldest_year = driver.execute_script("""
            const rows = document.querySelectorAll("table tbody tr");
            let minYear = null;
            for (const row of rows) {
                const cols = row.querySelectorAll("td");
                if (cols.length < 6) continue;
                const m = cols[5].textContent.trim().match(/\\b((?:19|20)\\d{2})\\b/);
                if (m) {
                    const yr = parseInt(m[1], 10);
                    if (minYear === null || yr < minYear) minYear = yr;
                }
            }
            return minYear;
        """)
        print(f"  Oldest year on page so far: {oldest_year}")
        if oldest_year is not None and oldest_year < min_year:
            print(f"  Year {oldest_year} is before target years {years} — stopping.")
            break

        page += 1


def scrape_and_upload(
    driver,
    gcs_client,
    gcs_prefix: str,
    search_url: str,
    years: list,
    bucket_name: str,
) -> None:
    """
    Filter table rows by year, scrape metadata, and upload PDFs to GCS.

    Author: Diane Woodbridge
    """
    year_set = set(years)
    data = driver.execute_script("""
        const rows = document.querySelectorAll("table tbody tr");
        const result = [];
        for (const row of rows) {
            const cols = row.querySelectorAll("td");
            if (cols.length < 6) continue;
            const a = cols[0].querySelector("a");
            if (!a) continue;
            result.push({
                href:       a.getAttribute("href") || "",
                case_no:    cols[1].textContent.trim(),
                date_filed: cols[5].textContent.trim()
            });
        }
        return result;
    """)

    filtered = [
        item for item in data
        if (m := re.search(r'\b((?:19|20)\d{2})\b', item["date_filed"]))
        and int(m.group(1)) in year_set
    ]
    print(f"  {len(filtered)} rows match years {years} (out of {len(data)} total)")

    for item in filtered:
        href = item["href"]
        if not href or href.startswith("javascript:") or not href.lower().endswith(".pdf"):
            continue
        case_no    = _safe_filename(item["case_no"])
        date_filed = _safe_filename(item["date_filed"])
        if not case_no or not date_filed:
            continue

        blob_name = f"{gcs_prefix}/{case_no}_{date_filed}.pdf"
        upload_to_gcs(gcs_client, bucket_name, blob_name, href)

        meta = scrape_metadata_for_case(item["case_no"], search_url)
        if meta:
            print(f"    {meta}")
        time.sleep(SCRAPE_DELAY)


def crawl(site_url: str, years: list, gcs_prefix: str) -> None:
    """
    Crawl the ca9 search page, upload matching PDFs to GCS, and print metadata.

    Uses Selenium to paginate through all pages for the given years, then
    uploads each PDF to GCS under gs://<GCP_BUCKET>/<gcs_prefix>/<case>_<date>.pdf.

    Args:
        site_url:   SEARCH_OPINIONS or SEARCH_MEMORANDA
        years:      list of int years to include, e.g. [2024, 2025, 2026]
        gcs_prefix: GCS folder prefix, e.g. "opinions" or "memoranda"

    Author: Diane Woodbridge
    """
    from google.cloud import storage
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    bucket_name = os.environ["GCP_BUCKET"]
    gcp_project = os.environ.get("GCP_PROJECT_ID")
    gcs_client  = storage.Client(project=gcp_project)

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(site_url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
        print(f"Page loaded. Expanding table for years {years}...")
        expand_all_pages(driver, years)
        print("Uploading PDFs to GCS...")
        scrape_and_upload(driver, gcs_client, gcs_prefix, site_url, years, bucket_name)
    finally:
        driver.quit()
        print("Browser closed.")


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
