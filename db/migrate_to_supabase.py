import argparse
import csv
import os
import sys
from typing import List, Dict, Any, Optional

from supabase import create_client, Client


DEFAULT_TABLE_NAME = "asylum_cases"
DEFAULT_FEATURES_CSV = "asylum_final_features.csv"
CONFLICT_COLUMN = "link"

# Columns that are typed as BOOLEAN in asylum_cases_schema.sql and need normalization
BOOLEAN_COLUMNS = [
    "asylum_requested",
    "withholding_requested",
    "CAT_requested",
    "protected_ground_race",
    "protected_ground_religion",
    "protected_ground_nationality",
    "protected_ground_political_opinion",
    "protected_ground_particular_social_group",
    "nexus_explicit_nexus_language",
    "nexus_nexus_strength",
    "past_persecution_established",
    "past_persecution_physical_violence",
    "past_persecution_detention",
    "past_persecution_sexual_violence",
    "past_persecution_death_threats",
    "past_persecution_harm_severity",
    "persecutor_government_actor",
    "persecutor_non_state_actor",
    "persecutor_government_unable_or_unwilling",
    "future_fear_well_founded_fear",
    "future_fear_internal_relocation_reasonable",
    "future_fear_changed_country_conditions",
    "credibility_credibility_finding",
    "credibility_inconsistencies_central",
    "credibility_corroboration_present",
    "country_conditions_cited",
    "bars_one_year_deadline_missed",
    "bars_firm_resettlement",
    "bars_particularly_serious_crime",
]


def get_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")

    if not url or not key:
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_SERVICE_KEY or SUPABASE_KEY")
        raise RuntimeError(
            f"Missing Supabase env vars: {', '.join(missing)}. "
            "Set them before running this script."
        )

    return create_client(url, key)


def load_features_csv(csv_path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Load feature rows from CSV. Returns list of dicts, one per row."""
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"Features CSV not found: {csv_path}")

    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            rows.append(dict(row))
    return rows


def records_from_csv(feature_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return rows that have a non-empty link (asylum_final_features.csv is source of truth).

    Also normalize boolean-typed columns:
      - empty string or whitespace -> None (NULL in Postgres)
      - \"true\"/\"t\"/\"1\" (case-insensitive) -> True
      - \"false\"/\"f\"/\"0\" (case-insensitive) -> False
    """
    records: List[Dict[str, Any]] = []
    for row in feature_rows:
        if not (row.get("link") or "").strip():
            print("Skipping row with empty link.", file=sys.stderr)
            continue
        normalized = dict(row)

        for col in BOOLEAN_COLUMNS:
            if col not in normalized:
                continue
            raw = (normalized.get(col) or "").strip()
            if raw == "":
                normalized[col] = None
                continue

            lower = raw.lower()
            if lower in ("true", "t", "1", "yes", "y"):
                normalized[col] = True
            elif lower in ("false", "f", "0", "no", "n"):
                normalized[col] = False
            else:
                # If value is unexpected, leave as-is to surface an error rather than silently coerce.
                normalized[col] = raw

        records.append(normalized)
    return records


def insert_batch(
    client: Client,
    table: str,
    batch: List[Dict[str, Any]],
    skip_on_conflict: bool = True,
    conflict_column: str = CONFLICT_COLUMN,
) -> None:
    if not batch:
        return

    # Supabase Python client does not support on_conflict() on insert().
    # To avoid duplicate-key errors on the unique link column, we use upsert()
    # with on_conflict=conflict_column. This will INSERT new rows and UPDATE
    # existing rows when a conflict on that column occurs.
    if skip_on_conflict:
        resp = client.table(table).upsert(batch, on_conflict=conflict_column).execute()
    else:
        resp = client.table(table).insert(batch).execute()

    # Surface any errors from Supabase.
    if getattr(resp, "error", None):
        raise RuntimeError(f"Supabase insert error: {resp.error}")


def migrate(
    table: str,
    features_csv: str,
    batch_size: int = 100,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> None:
    print(f"Features CSV: {features_csv}")
    print(f"Target table: {table}")

    feature_rows = load_features_csv(features_csv, limit=limit)
    if not feature_rows:
        print("No rows in CSV to migrate.")
        return

    records = records_from_csv(feature_rows)
    if not records:
        print("No records with link to migrate.")
        return

    print(f"Loaded {len(records)} row(s) from asylum_final_features.csv.")

    if dry_run:
        for r in records:
            print(f"[DRY RUN] Would migrate: {r.get('link', '')[:60]}...")
        return

    client = get_supabase_client()
    total = len(records)
    print(f"Inserting {total} record(s).")

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch = records[start:end]
        print(f"Inserting records {start + 1}-{end} of {total}...")
        insert_batch(client, table, batch)

    print("Migration complete.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Insert asylum_final_features.csv (single source of truth) into a Supabase table."
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE_NAME,
        help=f"Supabase table name to insert into (default: {DEFAULT_TABLE_NAME!r}).",
    )
    parser.add_argument(
        "--features-csv",
        default=DEFAULT_FEATURES_CSV,
        help=f"Path to asylum_final_features.csv (default: {DEFAULT_FEATURES_CSV!r}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of rows to insert per batch (default: 100).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit on number of CSV rows to migrate (useful for smoke tests).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List rows that would be inserted without writing to Supabase.",
    )

    args = parser.parse_args()

    try:
        migrate(
            table=args.table,
            features_csv=args.features_csv,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()