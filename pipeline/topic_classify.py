"""Topic-specific classification into separate asylum_cases_* tables.

Each target table isolates one concept extracted from the case PDF:
  - link               TEXT PRIMARY KEY REFERENCES asylum_cases(link)
  - {concept}          BOOLEAN
  - {concept}_evidence TEXT
  - extraction_model   TEXT
  - updated_at         TIMESTAMPTZ

When multiple tables are given, ONE LLM call is made per case PDF covering
all concepts simultaneously — avoiding redundant PDF uploads and reducing cost.

Usage:
  # Backfill pending rows (not yet in any target table)
  python topic_classify.py --tables asylum_cases_gang_opposition asylum_cases_machismo_opposition

  # Re-run all rows (overwrite existing)
  python topic_classify.py --tables asylum_cases_gang_opposition --all

  # Limit to N cases, oldest first
  python topic_classify.py --tables asylum_cases_gang_opposition --limit 20 --oldest-first

Env vars (same as extract.py):
  GOOGLE_APPLICATION_CREDENTIALS — service account key for Vertex AI
  MODEL_LABEL                    — Vertex AI model path
  PROVIDER_API_KEY / PROVIDER_BASE_URL / MODEL — for openai provider
  DATE_FROM / DATE_TO            — filter asylum_cases by date_filed
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client

# ── Concept registry ──────────────────────────────────────────────────────────
# Map from table name → human description used in the combined prompt.
# Field name = table name with "asylum_cases_" stripped.
# Evidence field = {concept}_evidence.

CONCEPT_REGISTRY: dict[str, str] = {
    "asylum_cases_gang_opposition": (
        "The applicant faced persecution specifically because they opposed, refused to join, "
        "resisted, or were perceived as a threat by a gang, criminal organization, or cartel. "
        "This includes family members targeted because of a relative's opposition to a gang."
    ),
    "asylum_cases_machismo_opposition": (
        "The applicant faced persecution related to gender-based violence, domestic violence, "
        "machismo culture, or resistance to patriarchal control — including femicide threats, "
        "forced relationships, or violence by an intimate partner or family member rooted in "
        "gender-based power dynamics."
    ),
}


def _concept_from_table(table: str) -> str:
    prefix = "asylum_cases_"
    if not table.startswith(prefix):
        raise ValueError(f"Table '{table}' must start with '{prefix}'")
    return table[len(prefix):]


def _build_combined_prompt(tables: list[str]) -> str:
    """Build one prompt covering all concepts. Returns JSON with 2 keys per concept."""
    for t in tables:
        if t not in CONCEPT_REGISTRY:
            raise ValueError(
                f"No concept description registered for '{t}'. "
                f"Add it to CONCEPT_REGISTRY in topic_classify.py."
            )

    definitions = "\n".join(
        f"{i + 1}. {_concept_from_table(t).upper()}: {CONCEPT_REGISTRY[t]}"
        for i, t in enumerate(tables)
    )

    json_keys = "\n".join(
        f'  "{_concept_from_table(t)}": true or false,\n'
        f'  "{_concept_from_table(t)}_evidence": '
        f'"quote from opinion if true, else \\"Not mentioned in the opinion.\\""'
        for t in tables
    )

    return f"""\
You are a legal document analyst. Read this asylum court decision PDF carefully.

For each concept below, determine whether it applies to this case.

CONCEPTS:
{definitions}

Return ONLY a valid JSON object with exactly these keys and no other text:
{{
{json_keys}
}}

Rules:
- Every boolean field MUST be true or false (never null).
- Every evidence field MUST be a non-empty string (never null).
"""


def fetch_pending_by_link(
    supabase,
    tables: list[str],
    run_all: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    oldest_first: bool = False,
    limit: int | None = None,
    links: list[str] | None = None,
) -> list[tuple[str, list[str]]]:
    """Return ordered list of (link, [tables_needing_this_link]).

    A link appears if it is pending in at least one table.
    If links is provided, only those links are considered (ignores date filters).
    In run_all mode every link is paired with all tables.
    """
    if links is not None:
        all_links = links
    else:
        query = supabase.table("asylum_cases").select("link")
        if date_from:
            query = query.gte("date_filed", date_from)
        if date_to:
            query = query.lte("date_filed", date_to)
        query = query.order("date_filed", desc=not oldest_first)
        all_links = [r["link"] for r in query.execute().data]

    if run_all:
        result = [(lnk, list(tables)) for lnk in all_links]
    else:
        existing_per_table: dict[str, set[str]] = {}
        for table in tables:
            rows = supabase.table(table).select("link").execute().data
            existing_per_table[table] = {r["link"] for r in rows}

        result = []
        for lnk in all_links:
            needed = [t for t in tables if lnk not in existing_per_table[t]]
            if needed:
                result.append((lnk, needed))

    if limit:
        result = result[:limit]
    return result


def _call_llm(link: str, prompt: str, provider: str, model_label: str,
              pdf_bytes: bytes | None = None) -> dict:
    """One LLM call for the given link. Returns parsed JSON dict.

    pdf_bytes: pass already-downloaded bytes to skip re-downloading.
    """
    import requests as req

    if provider == "gemini":
        from lib.gemini_client import send_pdf_to_gemini
        return send_pdf_to_gemini(link, prompt, model=model_label, pdf_bytes=pdf_bytes)

    # Text-based providers: extract PDF text first
    if pdf_bytes is None:
        resp = req.get(link, timeout=120)
        resp.raise_for_status()
        pdf_bytes = resp.content
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()

    from extract import _strip_reasoning_and_fences

    if provider == "cloudflare":
        r = req.post(
            f"{os.environ['PROVIDER_BASE_URL'].rstrip('/')}/{os.environ['MODEL']}",
            headers={"Authorization": f"Bearer {os.environ['PROVIDER_API_KEY']}"},
            json={"messages": [{"role": "user", "content": f"{prompt}\n\nOpinion text:\n{text}"}],
                  "max_tokens": 4096},
            timeout=120,
        )
        r.raise_for_status()
        raw = r.json()["result"]["response"]
    else:  # openai-compatible
        from openai import OpenAI
        client = OpenAI(base_url=os.environ["PROVIDER_BASE_URL"],
                        api_key=os.environ["PROVIDER_API_KEY"])
        raw = client.chat.completions.create(
            model=os.environ["MODEL"],
            messages=[{"role": "user", "content": f"{prompt}\n\nOpinion text:\n{text}"}],
            temperature=0,
        ).choices[0].message.content.strip()

    return json.loads(_strip_reasoning_and_fences(raw))


def run(
    tables: list[str],
    provider: str = "gemini",
    run_all: bool = False,
    date_from: str | None = None,
    date_to: str | None = None,
    oldest_first: bool = False,
    limit: int | None = None,
    links: list[str] | None = None,
    pdf_bytes_map: dict[str, bytes] | None = None,
) -> dict[str, int]:
    """Run topic classification. One LLM call per link covers all concepts.

    links:         restrict to these links (used by extract.py for new cases).
    pdf_bytes_map: pre-downloaded PDF bytes keyed by link — avoids re-downloading.
    Returns {table: count_processed}.
    """
    model_label = os.environ.get("MODEL_LABEL", "publishers/google/models/gemini-2.5-pro")
    supabase = get_client()

    combined_prompt = _build_combined_prompt(tables)

    pending = fetch_pending_by_link(
        supabase, tables,
        run_all=run_all, date_from=date_from, date_to=date_to,
        oldest_first=oldest_first, limit=limit, links=links,
    )

    mode = "all" if run_all else "pending"
    print(f"Found {len(pending)} links to process ({mode}) across {len(tables)} table(s)")

    counts = {t: 0 for t in tables}
    errors = 0
    now_str = datetime.now(timezone.utc).isoformat()

    for i, (link, link_tables) in enumerate(pending):
        print(f"[{i + 1}/{len(pending)}] {link}")

        # Rebuild prompt if this link only needs a subset of tables
        prompt = _build_combined_prompt(link_tables) if link_tables != tables else combined_prompt

        try:
            fields = _call_llm(link, prompt, provider, model_label,
                               pdf_bytes=pdf_bytes_map.get(link) if pdf_bytes_map else None)

            for table in link_tables:
                concept = _concept_from_table(table)
                evidence_field = f"{concept}_evidence"

                if concept not in fields:
                    print(f"  WARNING: model did not return '{concept}' — skipping {table}")
                    continue

                val = fields[concept]
                if isinstance(val, str):
                    val = val.strip().lower() == "true"

                row = {
                    "link": link,
                    concept: val,
                    evidence_field: fields.get(evidence_field, ""),
                    "extraction_model": model_label,
                    "updated_at": now_str,
                }
                supabase.table(table).upsert(row, on_conflict="link").execute()
                counts[table] += 1
                print(f"  -> [{table}] {concept}={val}")

        except json.JSONDecodeError as e:
            print(f"  ERROR: invalid JSON — {e}")
            errors += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            if any(code in str(e) for code in ("429", "402")):
                print("  Rate limit hit — stopping.")
                break

    print(f"\nDone — errors: {errors}")
    for table, count in counts.items():
        print(f"  {table}: {count} processed")

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Classify asylum cases into topic-specific tables (one LLM call per case)"
    )
    parser.add_argument(
        "--tables", nargs="+", required=True, metavar="TABLE",
        help="Target tables, e.g. asylum_cases_gang_opposition asylum_cases_machismo_opposition",
    )
    parser.add_argument(
        "--provider", choices=["gemini", "openai", "cloudflare"], default="gemini",
    )
    parser.add_argument(
        "--all", dest="run_all", action="store_true",
        help="Re-run all links (upsert), not just pending ones",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--date-from", default=os.environ.get("DATE_FROM"))
    parser.add_argument("--date-to", default=os.environ.get("DATE_TO"))
    parser.add_argument("--oldest-first", action="store_true",
                        default=bool(os.environ.get("OLDEST_FIRST")))
    args = parser.parse_args()

    run(
        tables=args.tables,
        provider=args.provider,
        run_all=args.run_all,
        date_from=args.date_from,
        date_to=args.date_to,
        oldest_first=args.oldest_first,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
