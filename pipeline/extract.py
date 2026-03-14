"""Extract structured legal features from asylum case PDFs using Gemini.

Reads pending asylum cases from asylum_cases (where court_level IS NULL),
sends each PDF to Gemini 2.5 Pro with a detailed extraction prompt,
and updates the asylum_cases row with extracted fields.
"""

import argparse
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.supabase_client import get_client
from lib.gemini_client import send_pdf_to_gemini


EXTRACTION_PROMPT = """\
You are a legal document analyst. Read this asylum court decision PDF carefully
and extract the following fields. Return ONLY a valid JSON object with exactly
these keys and no other text or explanation.

For boolean fields: use true, false, or null if not determinable.
For text fields: use a short string, or null if not present.

{
  "court_level": "string — e.g. Immigration Court, BIA, Circuit Court",
  "court_level_evidence": "string — quote or paraphrase supporting this",
  "country_of_origin": "string — country the applicant is from",
  "country_of_origin_evidence": "string — supporting text",
  "asylum_requested": true,
  "asylum_requested_evidence": "string",
  "withholding_requested": true,
  "withholding_requested_evidence": "string",
  "CAT_requested": true,
  "CAT_requested_evidence": "string",
  "final_disposition": "string — e.g. Granted, Denied, Remanded",
  "final_disposition_evidence": "string",
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


def fetch_pending_rows(supabase) -> list[dict]:
    """Fetch asylum_cases rows that still need feature extraction.

    Targets rows where court_level is NULL or empty string.
    """
    null_rows = (
        supabase.table("asylum_cases")
        .select("link")
        .is_("court_level", "null")
        .execute()
    )
    empty_rows = (
        supabase.table("asylum_cases")
        .select("link")
        .eq("court_level", "")
        .execute()
    )

    # Deduplicate by link
    seen = set()
    unique = []
    for row in null_rows.data + empty_rows.data:
        if row["link"] not in seen:
            seen.add(row["link"])
            unique.append(row)
    return unique


def run(limit: int | None = None) -> int:
    """Extract features for pending asylum cases. Returns count processed."""
    supabase = get_client()
    pending = fetch_pending_rows(supabase)

    if limit:
        pending = pending[:limit]

    print(f"Found {len(pending)} cases pending extraction")
    extracted = 0

    for i, row in enumerate(pending):
        link = row["link"]
        print(f"[{i + 1}/{len(pending)}] Extracting: {link}")

        try:
            fields = send_pdf_to_gemini(link, EXTRACTION_PROMPT)
            supabase.table("asylum_cases").update(fields).eq("link", link).execute()
            print(f"  -> extracted {len(fields)} fields")
            extracted += 1

        except json.JSONDecodeError as e:
            print(f"  ERROR: Gemini returned invalid JSON: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"Extracted features for {extracted} cases")
    return extracted


def main():
    parser = argparse.ArgumentParser(
        description="Extract legal features from asylum case PDFs using Gemini"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of cases to process (default: all pending)",
    )
    args = parser.parse_args()
    run(limit=args.limit)


if __name__ == "__main__":
    main()
