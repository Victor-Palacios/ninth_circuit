import csv
import datetime
import os
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")  # your secret role key

# ── Export ────────────────────────────────────────────────────────────────────
def export_to_csv():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    result = supabase.table("asylum_cases").select("*").execute()

    if not result.data:
        print("No data found.")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"asylum_cases_run_{timestamp}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=result.data[0].keys())
        writer.writeheader()
        writer.writerows(result.data)

    print(f"✓ Exported {len(result.data)} rows to {filename}")


if __name__ == "__main__":
    export_to_csv()