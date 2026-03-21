"""Extract structured legal features from asylum case PDFs.

Supports two modes:
  - gemini (default): sends PDF bytes to Gemini 2.5 Pro via Vertex AI
  - openai-compatible: extracts text and sends via OpenAI-compatible API
    (OpenRouter, HuggingFace, Groq, etc.) configured by env vars

Reads pending asylum cases from asylum_cases (where char_count IS NULL),
sends each PDF to the chosen model with a detailed extraction prompt,
and updates the asylum_cases row with extracted fields plus
extraction_model and extracted_at metadata.

Env vars for openai-compatible providers:
  PROVIDER_API_KEY   — API key for the provider
  PROVIDER_BASE_URL  — OpenAI-compatible base URL
  MODEL              — model name to use in API call
  MODEL_LABEL        — value stored in extraction_model column
  DATE_FROM          — filter: date_filed >= this (YYYY-MM-DD)
  DATE_TO            — filter: date_filed <= this (YYYY-MM-DD)
  OLDEST_FIRST       — if set, sort by date_filed ascending
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import pymupdf
import requests

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client


EXTRACTION_PROMPT = """\
You are a legal document analyst. Read this asylum court decision PDF carefully
and extract the following fields. Return ONLY a valid JSON object with exactly
these keys and no other text or explanation.

RULES — follow these strictly, no exceptions:
1. Boolean fields: ALWAYS return true or false. Never return null.
   - Return true if the topic is present or applicable in the opinion.
   - Return false if the topic is absent, not raised, or not addressed.
2. Evidence fields: ALWAYS return a non-empty string. Never return null.
   - If the boolean is true: quote the most relevant sentence(s) from the opinion.
   - If the boolean is false: write "Not mentioned in the opinion."
3. Text fields (country_of_origin, final_disposition): ALWAYS return a non-empty string.
   - If genuinely unknown after reading the full document, write "Not determined."
4. Every single key in the JSON must have a non-null value. Null is never acceptable.

{
  "country_of_origin": "string — country the applicant is from",
  "country_of_origin_evidence": "string — direct quote from the opinion",
  "asylum_requested": true,
  "asylum_requested_evidence": "string",
  "withholding_requested": true,
  "withholding_requested_evidence": "string",
  "CAT_requested": true,
  "CAT_requested_evidence": "string",
  "final_disposition": "string — e.g. Granted, Denied, Remanded, Dismissed",
  "final_disposition_evidence": "string — direct quote from the opinion",
  "protected_ground_race": true,
  "protected_ground_race_evidence": "string",
  "protected_ground_religion": true,
  "protected_ground_religion_evidence": "string",
  "protected_ground_nationality": true,
  "protected_ground_nationality_evidence": "string",
  "protected_ground_political_opinion": true,
  "protected_ground_political_opinion_evidence": "string",
  "protected_ground_particular_social_group": true,
  "protected_ground_particular_social_group_evidence": "string",
  "nexus_explicit_nexus_language": true,
  "nexus_explicit_nexus_language_evidence": "string",
  "nexus_nexus_strength": true,
  "nexus_nexus_strength_evidence": "string",
  "past_persecution_established": true,
  "past_persecution_established_evidence": "string",
  "past_persecution_physical_violence": true,
  "past_persecution_physical_violence_evidence": "string",
  "past_persecution_detention": true,
  "past_persecution_detention_evidence": "string",
  "past_persecution_sexual_violence": true,
  "past_persecution_sexual_violence_evidence": "string",
  "past_persecution_death_threats": true,
  "past_persecution_death_threats_evidence": "string",
  "past_persecution_harm_severity": true,
  "past_persecution_harm_severity_evidence": "string",
  "persecutor_government_actor": true,
  "persecutor_government_actor_evidence": "string",
  "persecutor_non_state_actor": true,
  "persecutor_non_state_actor_evidence": "string",
  "persecutor_government_unable_or_unwilling": true,
  "persecutor_government_unable_or_unwilling_evidence": "string",
  "future_fear_well_founded_fear": true,
  "future_fear_well_founded_fear_evidence": "string",
  "future_fear_internal_relocation_reasonable": true,
  "future_fear_internal_relocation_reasonable_evidence": "string",
  "future_fear_changed_country_conditions": true,
  "future_fear_changed_country_conditions_evidence": "string",
  "credibility_credibility_finding": true,
  "credibility_credibility_finding_evidence": "string",
  "credibility_inconsistencies_central": true,
  "credibility_inconsistencies_central_evidence": "string",
  "credibility_corroboration_present": true,
  "credibility_corroboration_present_evidence": "string",
  "country_conditions_cited": true,
  "country_conditions_cited_evidence": "string",
  "bars_one_year_deadline_missed": true,
  "bars_one_year_deadline_missed_evidence": "string",
  "bars_firm_resettlement": true,
  "bars_firm_resettlement_evidence": "string",
  "bars_particularly_serious_crime": true,
  "bars_particularly_serious_crime_evidence": "string"
}
"""


def download_pdf(url: str) -> bytes:
    """Download a PDF into memory. Returns raw bytes."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def _strip_reasoning_and_fences(raw: str) -> str:
    """Strip <think> blocks and markdown fences from model output."""
    import re
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return raw


def send_text_to_cloudflare(text: str, prompt: str) -> dict:
    """Send extracted PDF text to Cloudflare Workers AI native endpoint.

    Reads PROVIDER_API_KEY, PROVIDER_BASE_URL, and MODEL from env vars.
    PROVIDER_BASE_URL should be the /ai/run/ base (not /ai/v1/).
    Returns the parsed JSON response as a dict.
    """
    api_key = os.environ.get("PROVIDER_API_KEY")
    base_url = os.environ.get("PROVIDER_BASE_URL", "").rstrip("/")
    model = os.environ.get("MODEL")

    for var, name in [(api_key, "PROVIDER_API_KEY"), (base_url, "PROVIDER_BASE_URL"),
                      (model, "MODEL")]:
        if not var:
            raise RuntimeError(f"{name} is not set.")

    resp = requests.post(
        f"{base_url}/{model}",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"messages": [
            {"role": "user", "content": f"{prompt}\n\nOpinion text:\n{text}"}
        ], "max_tokens": 16384},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    raw = data["result"]["response"]
    return json.loads(_strip_reasoning_and_fences(raw))


def send_text_to_provider(text: str, prompt: str) -> dict:
    """Send extracted PDF text to an OpenAI-compatible provider.

    Reads PROVIDER_API_KEY, PROVIDER_BASE_URL, and MODEL from env vars.
    Returns the parsed JSON response as a dict.
    """
    from openai import OpenAI

    api_key = os.environ.get("PROVIDER_API_KEY")
    base_url = os.environ.get("PROVIDER_BASE_URL")
    model = os.environ.get("MODEL")

    for var, name in [(api_key, "PROVIDER_API_KEY"), (base_url, "PROVIDER_BASE_URL"),
                      (model, "MODEL")]:
        if not var:
            raise RuntimeError(f"{name} is not set.")

    client = OpenAI(base_url=base_url, api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": f"{prompt}\n\nOpinion text:\n{text}"}
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()
    return json.loads(_strip_reasoning_and_fences(raw))


def fetch_pending_rows(supabase, limit: int | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None,
                       oldest_first: bool = False) -> list[dict]:
    """Fetch asylum_cases rows that still need feature extraction.

    Targets rows where char_count is NULL — the most reliable indicator
    that a row has never been through extraction.  Optionally filters by
    date_filed range and controls sort direction.
    """
    query = (
        supabase.table("asylum_cases")
        .select("link")
        .is_("char_count", "null")
    )
    if date_from:
        query = query.gte("date_filed", date_from)
    if date_to:
        query = query.lte("date_filed", date_to)
    query = query.order("date_filed", desc=not oldest_first)
    if limit:
        query = query.limit(limit)
    return query.execute().data


def run(limit: int | None = None, provider: str = "gemini",
        date_from: str | None = None, date_to: str | None = None,
        oldest_first: bool = False) -> int:
    """Extract features for pending asylum cases. Returns count processed."""
    model_label = os.environ.get("MODEL_LABEL", "gemini-2.5-pro") if provider != "gemini" else "gemini-2.5-pro"

    # Configure MLflow if DATABASE_URL is set
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        mlflow.set_tracking_uri(db_url)
    mlflow.set_experiment("extraction")

    supabase = get_client()
    pending = fetch_pending_rows(supabase, limit=limit, date_from=date_from,
                                 date_to=date_to, oldest_first=oldest_first)

    range_str = f" ({date_from} to {date_to})" if date_from or date_to else ""
    print(f"Found {len(pending)} cases pending extraction{range_str} (provider: {provider})")
    extracted = 0
    errors = 0
    error_lines: list[str] = []
    success_links: list[str] = []

    with mlflow.start_run():
        mlflow.log_param("model", model_label)
        mlflow.log_param("provider", provider)
        mlflow.log_param("limit", limit)
        mlflow.log_param("date_from", date_from or "all")
        mlflow.log_param("date_to", date_to or "all")
        mlflow.log_param("oldest_first", oldest_first)
        mlflow.log_param("pending_count", len(pending))
        mlflow.log_text(EXTRACTION_PROMPT, "prompt.txt")

        total_chars = 0

        for i, row in enumerate(pending):
            link = row["link"]
            print(f"[{i + 1}/{len(pending)}] Extracting: {link}")

            try:
                pdf_bytes = download_pdf(link)
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                text = "".join(page.get_text() for page in doc)
                doc.close()
                char_count = len(text)

                if provider == "cloudflare":
                    fields = send_text_to_cloudflare(text, EXTRACTION_PROMPT)
                elif provider == "openai":
                    fields = send_text_to_provider(text, EXTRACTION_PROMPT)
                else:
                    from lib.gemini_client import send_pdf_to_gemini
                    fields = send_pdf_to_gemini(link, EXTRACTION_PROMPT, pdf_bytes=pdf_bytes)

                fields["char_count"] = char_count
                fields["extraction_model"] = model_label
                fields["extracted_at"] = datetime.now(timezone.utc).isoformat()
                supabase.table("asylum_cases").update(fields).eq("link", link).execute()
                print(f"  -> extracted {len(fields)} fields ({char_count:,} chars)")
                extracted += 1
                total_chars += char_count
                success_links.append(link)

            except json.JSONDecodeError as e:
                msg = f"Invalid JSON: {e}"
                print(f"  ERROR: model returned {msg}")
                errors += 1
                error_lines.append(f"{link} — {msg}")
            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1
                error_lines.append(f"{link} — {e}")
                if "Error code: 429" in str(e) or "Error code: 402" in str(e):
                    print("  Rate limit or quota exhausted — stopping early.")
                    break

        # Estimate cost (Gemini only; OpenRouter free tier = $0)
        if provider == "gemini":
            estimated_cost = extracted * ((3250 * 1.25 + 3650 * 10) / 1_000_000)
        else:
            estimated_cost = 0.0

        mlflow.log_metric("extracted", extracted)
        mlflow.log_metric("errors", errors)
        mlflow.log_metric("total_chars", total_chars)
        mlflow.log_metric("avg_chars", total_chars / extracted if extracted else 0)
        mlflow.log_metric("estimated_cost_usd", round(estimated_cost, 4))

    # Write summary file for email notifications
    summary_path = os.environ.get("SUMMARY_FILE", "extract_summary.txt")
    with open(summary_path, "w") as f:
        f.write(f"Extracted: {extracted}  Errors: {errors}  Pending: {len(pending)}\n")
        f.write(f"Provider: {provider}  Model: {model_label}\n")
        if error_lines:
            f.write(f"\nERRORS ({len(error_lines)}):\n")
            for line in error_lines:
                f.write(f"  {line}\n")
        for link in success_links:
            f.write(f"{link}\n")

    print(f"Extracted features for {extracted} cases")
    return extracted


def main():
    parser = argparse.ArgumentParser(
        description="Extract legal features from asylum case PDFs"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of cases to process (default: all pending)",
    )
    parser.add_argument(
        "--provider",
        choices=["gemini", "openai", "cloudflare"],
        default="gemini",
        help="LLM provider: gemini (Vertex AI) or openai (OpenAI-compatible via env vars)",
    )
    parser.add_argument(
        "--date-from",
        default=os.environ.get("DATE_FROM"),
        help="Filter: date_filed >= this (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--date-to",
        default=os.environ.get("DATE_TO"),
        help="Filter: date_filed <= this (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--oldest-first",
        action="store_true",
        default=bool(os.environ.get("OLDEST_FIRST")),
        help="Sort by date_filed ascending (oldest first)",
    )
    args = parser.parse_args()
    run(limit=args.limit, provider=args.provider,
        date_from=args.date_from, date_to=args.date_to,
        oldest_first=args.oldest_first)


if __name__ == "__main__":
    main()
