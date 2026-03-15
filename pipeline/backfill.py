"""Backfill historical opinions from ca9.uscourts.gov via DynamoDB.

The ca9 website stores opinions in AWS DynamoDB and exposes them via
public Cognito credentials.  This script queries DynamoDB directly
(the same way the browser does) to pull opinions within a date range,
then upserts them into the all_opinions table in Supabase.

Usage:
    python -m pipeline.backfill --start-date 2025-01-01 --end-date 2026-03-14
    python -m pipeline.backfill --start-date 2026-01-01 --end-date 2026-02-12 --no-classify --no-extract
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from pipeline import classify, extract


# Public Cognito credentials (embedded in the ca9 website JavaScript)
COGNITO_IDENTITY_POOL_ID = "us-west-2:31f0d3b4-d5da-4a0d-aaa4-dc5c55a9156f"
AWS_REGION = "us-west-2"

# DynamoDB tables (one for published opinions, one for unpublished memoranda)
DYNAMO_TABLES = {
    "opinions": "Published",
    "memoranda": "Unpublished",
}

SUPABASE_TABLE = "all_opinions"


def get_dynamo_client():
    """Create a DynamoDB client using the ca9 public Cognito credentials."""
    cognito = boto3.client("cognito-identity", region_name=AWS_REGION)
    identity = cognito.get_id(IdentityPoolId=COGNITO_IDENTITY_POOL_ID)
    credentials = cognito.get_credentials_for_identity(
        IdentityId=identity["IdentityId"]
    )["Credentials"]

    session = boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=AWS_REGION,
    )
    return session.resource("dynamodb")


def date_to_publish_ts(dt: datetime) -> int:
    """Convert a datetime to the integer timestamp format ca9 uses in DynamoDB.

    The 'publish' field is stored as a numeric string representing
    YYYYMMDD * 100000 (giving room for intra-day ordering).
    """
    return int(dt.strftime("%Y%m%d")) * 1000000


def scan_table(
    dynamo,
    table_name: str,
    start_date: datetime,
    end_date: datetime,
    published_status: str,
) -> list[dict]:
    """Scan a ca9 DynamoDB table for opinions in a date range.

    Returns a list of dicts ready for Supabase insertion.
    """
    table = dynamo.Table(table_name)
    pub_start = date_to_publish_ts(start_date)
    pub_end = date_to_publish_ts(end_date + timedelta(days=1))  # inclusive end

    filter_expr = (
        Attr("publish").gte(pub_start)
        & Attr("publish").lte(pub_end)
        & Attr("deleted").eq("0")
    )

    projection = "file_name,case_name,case_num,case_origin,judge,case_type,short_date"

    opinions = []
    scan_kwargs = {
        "FilterExpression": filter_expr,
        "ProjectionExpression": projection,
    }

    page = 0
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])
        page += 1

        for item in items:
            file_name = item.get("file_name", "")
            if not file_name:
                continue

            # Build the PDF link
            # file_name already contains the path like /datastore/opinions/2026/01/02/...
            if file_name.startswith("/"):
                link = f"https://cdn.ca9.uscourts.gov{file_name}"
            elif file_name.startswith("http"):
                link = file_name
            else:
                link = f"https://cdn.ca9.uscourts.gov/{file_name}"

            # Parse the date (MM/DD/YYYY)
            date_filed = None
            short_date = item.get("short_date", "")
            if short_date:
                try:
                    dt = datetime.strptime(short_date, "%m/%d/%Y")
                    date_filed = dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

            opinions.append({
                "link": link,
                "case_title": item.get("case_name") or None,
                "case_number": item.get("case_num") or None,
                "case_origin": item.get("case_origin") or None,
                "authoring_judge": item.get("judge") or None,
                "case_type": item.get("case_type") or None,
                "date_filed": date_filed,
                "published_status": published_status,
            })

        # Handle pagination
        if "LastEvaluatedKey" in response:
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            print(f"    Page {page}: {len(items)} items (scanning more...)")
        else:
            print(f"    Page {page}: {len(items)} items (done)")
            break

    return opinions


def backfill(
    start_date: str,
    end_date: str,
    classify_after: bool = True,
    extract_after: bool = True,
):
    """Backfill opinions for a date range.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        classify_after: Run classification after inserting
        extract_after: Run extraction after classifying
    """
    supabase = get_client()
    dynamo = get_dynamo_client()

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    print(f"Backfilling {start_date} to {end_date}")
    print(f"Authenticating with ca9 DynamoDB via Cognito...\n")

    total_inserted = 0

    for dynamo_table, published_status in DYNAMO_TABLES.items():
        print(f"--- Scanning '{dynamo_table}' table ({published_status}) ---")
        opinions = scan_table(dynamo, dynamo_table, start, end, published_status)
        print(f"  Found {len(opinions)} {published_status.lower()} opinions\n")

        if not opinions:
            continue

        # Upsert in batches of 500 (Supabase limit)
        batch_size = 500
        for i in range(0, len(opinions), batch_size):
            batch = opinions[i : i + batch_size]
            try:
                result = supabase.table(SUPABASE_TABLE).upsert(
                    batch, on_conflict="link"
                ).execute()
                inserted = len(result.data)
                total_inserted += inserted
                print(f"  Upserted batch {i // batch_size + 1}: {inserted} rows")
            except Exception as e:
                print(f"  ERROR inserting batch: {e}")
                if "storage" in str(e).lower() or "quota" in str(e).lower():
                    print("  Supabase storage limit likely reached. Stopping.")
                    return

    print(f"\nBackfill complete. Total rows inserted/updated: {total_inserted}")

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
        default="2025-01-01",
        help="Start date YYYY-MM-DD (default: 2025-01-01)",
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
