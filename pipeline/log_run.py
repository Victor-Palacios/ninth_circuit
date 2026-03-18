"""Append a classifier run result row to logs/classify_{provider}.csv.

Usage: python pipeline/log_run.py <provider_name>
  provider_name: huggingface | groq | openrouter

Reads CLASSIFY_SUMMARY_FILE env var (default: classify_summary.txt).
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone

provider = sys.argv[1]
summary_file = os.environ.get("CLASSIFY_SUMMARY_FILE", "classify_summary.txt")

now = datetime.now(timezone.utc)
found, classified, asylum = 0, 0, 0
try:
    for line in open(summary_file).read().splitlines():
        m = re.search(r"Classified (\d+)/(\d+)", line)
        if m:
            classified, found = int(m.group(1)), int(m.group(2))
        m = re.search(r"Asylum-related: (\d+)", line)
        if m:
            asylum = int(m.group(1))
except FileNotFoundError:
    pass

log_file = f"logs/classify_{provider}.csv"
with open(log_file, "a", newline="") as f:
    csv.writer(f).writerow([
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        found,
        classified,
        asylum,
    ])
print(f"Logged to {log_file}: {found} found, {classified} classified, {asylum} asylum")
