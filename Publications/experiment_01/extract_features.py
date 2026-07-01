"""Experiment 1 — probe 3 NVIDIA NIM models on 11 binary features per sample PDF.

Adapted from evaluation/nvidia_features.py. Differences:
  - 11 features (adds `nexus_requirement_met`)
  - definitions per the Experiment 1 codebook (see human_labeling_instructions.md)
  - output lives beside this script

Features (one LLM call per (case, model) returns all 11 at once):
  asylum_requested
  withholding_requested
  CAT_requested
  protected_ground_political_opinion
  protected_ground_particular_social_group
  past_persecution_physical_violence
  past_persecution_death_threats
  persecutor_nongovernmental_actor
  credibility_finding            (categorical: favorable | adverse | mixed | none)
  bars_one_year_deadline_missed
  nexus_requirement_met

Pydantic enforces booleans (and the categorical credibility_finding);
evidence quotes are free-form strings.

Output (long format, 30 PDFs * 3 models * 11 features = 990 rows):
  Publications/experiment_01/results/features.csv
  Columns: case_id, pdf_url, model, feature, predicted, evidence, latency_ms, error

Env:
  NVIDIA_API_KEY — nvapi-... key

Usage:
  set -a && source .env && set +a && source ninthc/bin/activate \
    && python3 Publications/experiment_01/extract_features.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
import pymupdf
import requests
from openai import OpenAI
from typing import Literal

from pydantic import BaseModel, ValidationError

# This file lives at Publications/experiment_01/ ; repo root is two levels up.
EXP_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

SAMPLE_CSV = REPO_ROOT / "reports" / "sample_30_cases.csv"
OUT_CSV = EXP_DIR / "results" / "features.csv"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODELS = [
    "meta/llama-3.3-70b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "mistralai/mistral-large-3-675b-instruct-2512",
]

# (feature_name, definition shown to the model) — Experiment 1 codebook.
FEATURES: list[tuple[str, str]] = [
    ("asylum_requested",
     "Petitioner applied for asylum under INA § 208 / 8 U.S.C. § 1158, not just "
     "withholding of removal or CAT protection."),
    ("withholding_requested",
     "Petitioner sought withholding of removal under INA § 241(b)(3)."),
    ("CAT_requested",
     "Petitioner sought protection under the Convention Against Torture under "
     "8 C.F.R. §§ 1208.16-1208.18."),
    ("protected_ground_political_opinion",
     "The claim is based at least in part on actual or imputed political opinion."),
    ("protected_ground_particular_social_group",
     "The claim is based at least in part on membership in a particular social group, or PSG."),
    ("past_persecution_physical_violence",
     "The record describes past physical violence inflicted on the petitioner, such as "
     "beatings, shootings, stabbings, or similar harm."),
    ("past_persecution_death_threats",
     "The record describes death threats made against the petitioner."),
    ("persecutor_nongovernmental_actor",
     "The text indicates that past persecution was, or was feared to be, carried out by a "
     "non-government actor."),
    ("credibility_finding",
     "The IJ or BIA made an explicit credibility determination about the petitioner. "
     "Report it as one of: favorable, adverse, or mixed. Report none if the opinion "
     "contains no explicit credibility determination."),
    ("bars_one_year_deadline_missed",
     "The opinion notes that the petitioner missed the one-year asylum filing deadline "
     "under INA § 208(a)(2)(B)."),
    ("nexus_requirement_met",
     "The IJ or BIA found that the petitioner established the required nexus: that a "
     "protected ground was, or would be, 'at least one central reason' for the persecution, "
     "as required by INA § 208(b)(1)(B)(i). (For withholding of removal, the lower "
     "'a reason' standard applies.)"),
]

FEATURE_NAMES = [name for name, _ in FEATURES]

# Features that are categorical rather than boolean: name -> allowed values.
CATEGORICAL: dict[str, list[str]] = {
    "credibility_finding": ["favorable", "adverse", "mixed", "none"],
}

OUT_COLUMNS = [
    "case_id", "pdf_url", "model", "feature",
    "predicted", "evidence", "latency_ms", "error",
]


def build_prompt() -> str:
    field_lines = [f"  - {name}: {defn}" for name, defn in FEATURES]
    feature_block = "\n".join(field_lines)

    schema_lines = []
    for name, _ in FEATURES:
        if name in CATEGORICAL:
            opts = " | ".join(f'"{o}"' for o in CATEGORICAL[name])
            schema_lines.append(f'  "{name}": {opts},')
        else:
            schema_lines.append(f'  "{name}": true | false,')
        schema_lines.append(f'  "{name}_evidence": "<verbatim quote from the opinion, or \'Not mentioned in the opinion.\' if false/none>",')
    schema_block = "\n".join(schema_lines).rstrip(",")

    cat_rules = "".join(
        f'- "{name}" MUST be exactly one of: {", ".join(CATEGORICAL[name])}.\n'
        for name in CATEGORICAL
    )

    return (
        "You are a legal document analyst reading a Ninth Circuit asylum-related opinion.\n\n"
        "For each feature below, return the specified JSON value (a boolean unless the\n"
        "schema shows a fixed set of string options) and a one-sentence verbatim evidence\n"
        "quote from the opinion. If a boolean is false, or a categorical is \"none\", the\n"
        "evidence value MUST be exactly the string \"Not mentioned in the opinion.\"\n\n"
        "FEATURES:\n"
        f"{feature_block}\n\n"
        f"Return ONLY a JSON object with exactly these {len(FEATURES) * 2} keys and no other text:\n"
        "{\n"
        f"{schema_block}\n"
        "}\n\n"
        "RULES:\n"
        "- Every feature field is a JSON boolean EXCEPT the categorical fields below.\n"
        f"{cat_rules}"
        "- Never return null. Never return a string for a boolean field.\n"
        "- Quote evidence verbatim from the opinion. Do not paraphrase."
    )


PROMPT = build_prompt()


def build_model() -> type[BaseModel]:
    from pydantic import create_model
    fields: dict[str, tuple] = {}
    for name, _ in FEATURES:
        if name in CATEGORICAL:
            fields[name] = (Literal[tuple(CATEGORICAL[name])], ...)  # type: ignore
        else:
            fields[name] = (bool, ...)
        fields[f"{name}_evidence"] = (str, "")
    return create_model("FeatureResult", **fields)  # type: ignore


FeatureResult = build_model()


def case_id_from_url(url: str) -> str:
    """Unique case id: docket stem + filing date (YYYY-MM-DD) from the CA9 URL."""
    parts = [p for p in url.split("/") if p]
    stem = Path(url).stem
    if len(parts) >= 4 and parts[-4].isdigit() and parts[-3].isdigit() and parts[-2].isdigit():
        yyyy, mm, dd = parts[-4], parts[-3], parts[-2]
        return f"{stem}-{yyyy}-{mm}-{dd}"
    return stem


def extract_pdf_text(url: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    doc = pymupdf.open(stream=resp.content, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return text


def strip_fences(raw: str) -> str:
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return raw


def call_model(client: OpenAI, model: str, pdf_text: str) -> BaseModel:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": f"{PROMPT}\n\nOPINION:\n{pdf_text}"}],
        temperature=0,
        response_format={"type": "json_object"},
        max_tokens=4096,
    )
    raw = strip_fences(resp.choices[0].message.content or "")
    data = json.loads(raw)
    return FeatureResult.model_validate(data)


def explode_to_rows(case_id: str, pdf_url: str, model: str,
                    result: BaseModel | None, latency_ms: int | None,
                    err: str) -> list[dict]:
    rows: list[dict] = []
    if result is None:
        for name in FEATURE_NAMES:
            rows.append({
                "case_id": case_id, "pdf_url": pdf_url, "model": model,
                "feature": name, "predicted": None, "evidence": "",
                "latency_ms": latency_ms, "error": err,
            })
        return rows

    data = result.model_dump()
    for name in FEATURE_NAMES:
        rows.append({
            "case_id": case_id, "pdf_url": pdf_url, "model": model,
            "feature": name,
            "predicted": data[name],
            "evidence": data.get(f"{name}_evidence", "") or "",
            "latency_ms": latency_ms, "error": "",
        })
    return rows


def flush(rows: list[dict]) -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    tmp = OUT_CSV.with_suffix(".csv.tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(OUT_CSV)


def load_checkpoint() -> tuple[list[dict], set[tuple[str, str]]]:
    """Load any existing OUT_CSV. Returns (rows, done) where `done` is the set of
    (case_id, model) pairs that already succeeded (no error) and can be skipped."""
    if not OUT_CSV.exists():
        return [], set()
    df = pd.read_csv(OUT_CSV)
    df["error"] = df["error"].fillna("")
    df["evidence"] = df["evidence"].fillna("")
    rows = df.to_dict("records")
    done = {(r["case_id"], r["model"]) for r in rows if str(r.get("error", "")) == ""}
    return rows, done


def main() -> None:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set.")

    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)

    cases = pd.read_csv(SAMPLE_CSV)[["link"]].to_dict("records")
    print(f"Loaded {len(cases)} cases from {SAMPLE_CSV.name}")
    print(f"Models : {', '.join(MODELS)}")
    print(f"Features ({len(FEATURE_NAMES)}): {', '.join(FEATURE_NAMES)}")

    rows, done = load_checkpoint()
    if done:
        print(f"Resuming: {len(done)} (case, model) combos already complete; skipping those.")

    pdf_cache: dict[str, str] = {}

    for i, row in enumerate(cases, 1):
        url = row["link"]
        cid = case_id_from_url(url)

        pending_models = [m for m in MODELS if (cid, m) not in done]
        if not pending_models:
            print(f"\n[{i}/{len(cases)}] {cid}  (all models done, skipping)")
            continue

        print(f"\n[{i}/{len(cases)}] {cid}")

        try:
            if url not in pdf_cache:
                pdf_cache[url] = extract_pdf_text(url)
            text = pdf_cache[url]
            print(f"  pdf chars: {len(text):,}")
        except Exception as e:
            print(f"  ERROR downloading PDF: {e}")
            for model in pending_models:
                rows.extend(explode_to_rows(cid, url, model, None, None, f"pdf_download: {e}"))
            flush(rows)
            continue

        for model in pending_models:
            t0 = time.perf_counter()
            err = ""
            result: BaseModel | None = None
            try:
                result = call_model(client, model, text)
            except (json.JSONDecodeError, ValidationError) as e:
                err = f"parse: {type(e).__name__}: {e}"
            except Exception as e:
                err = f"api: {type(e).__name__}: {e}"
            lat = int((time.perf_counter() - t0) * 1000)

            if result is not None:
                trues = sum(1 for n in FEATURE_NAMES if n not in CATEGORICAL and getattr(result, n))
                cred = getattr(result, "credibility_finding", "?")
                print(f"  {model:<55} -> {trues:>2} bool-True, credibility={cred}  ({lat} ms)")
                done.add((cid, model))
            else:
                print(f"  {model:<55} -> ERROR  ({lat} ms): {err[:80]}")

            rows = [r for r in rows if not (r["case_id"] == cid and r["model"] == model)]
            rows.extend(explode_to_rows(cid, url, model, result, lat, err))
            flush(rows)
            time.sleep(1.2)  # gentle on the NVIDIA free-tier rate limit

    out_df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    print(f"\nWrote {len(out_df)} rows -> {OUT_CSV.relative_to(REPO_ROOT)}")

    print("\nSummary by model:")
    for model in MODELS:
        sub = out_df[out_df["model"] == model]
        ok = sub[sub["error"] == ""]
        n_cases_ok = ok["case_id"].nunique()
        n_true = int((ok["predicted"] == True).sum())
        n_false = int((ok["predicted"] == False).sum())
        n_err_cases = sub[sub["error"] != ""]["case_id"].nunique()
        print(f"  {model:<55} cases_ok={n_cases_ok:>2}  true={n_true:>3}  "
              f"false={n_false:>3}  cases_err={n_err_cases:>2}")


if __name__ == "__main__":
    main()
