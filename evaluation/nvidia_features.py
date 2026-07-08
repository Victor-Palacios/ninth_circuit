"""Probe 3 NVIDIA NIM models on 10 binary features per sample PDF.

Features (one LLM call per (case, model) returns all 10 at once):
  asylum_requested
  withholding_requested
  CAT_requested
  protected_ground_political_opinion
  protected_ground_particular_social_group
  past_persecution_physical_violence
  past_persecution_death_threats
  persecutor_nongovernmental_actor
  credibility_credibility_finding
  bars_one_year_deadline_missed

Pydantic enforces booleans; evidence quotes are free-form strings.

Output (long format, 30 PDFs * 3 models * 10 features = 900 rows):
  evaluation/results/nvidia_features.csv
  Columns: case_id, pdf_url, model, feature, predicted, evidence,
           latency_ms, error

Env:
  NVIDIA_API_KEY — nvapi-... key

Usage:
  set -a && source .env && set +a && source ninthc/bin/activate \
    && python3 evaluation/nvidia_features.py
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
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_CSV = REPO_ROOT / "Publications" / "sample_30_cases.csv"
OUT_CSV = REPO_ROOT / "evaluation" / "results" / "nvidia_features.csv"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODELS = [
    "meta/llama-3.3-70b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "mistralai/mistral-large-3-675b-instruct-2512",
]

# (feature_name, one-line definition shown to the model)
FEATURES: list[tuple[str, str]] = [
    ("asylum_requested",
     "petitioner applied for asylum (INA § 208 / 8 U.S.C. § 1158), not just withholding or CAT."),
    ("withholding_requested",
     "petitioner sought withholding of removal under INA § 241(b)(3)."),
    ("CAT_requested",
     "petitioner sought protection under the Convention Against Torture (8 C.F.R. § 1208.16-18)."),
    ("protected_ground_political_opinion",
     "the claim is based at least in part on actual or imputed political opinion."),
    ("protected_ground_particular_social_group",
     "the claim is based at least in part on membership in a particular social group (PSG)."),
    ("past_persecution_physical_violence",
     "the record describes past physical violence inflicted on the petitioner (beatings, shootings, stabbings, etc.)."),
    ("past_persecution_death_threats",
     "the record describes death threats made against the petitioner."),
    ("persecutor_nongovernmental_actor",
     "Whether the text indicates that past persecution was or was feared to have been carried out by a non-government actor."),
    ("credibility_credibility_finding",
     "the IJ or BIA made an explicit credibility finding about the petitioner (favorable or adverse)."),
    ("bars_one_year_deadline_missed",
     "the opinion notes the petitioner missed the one-year asylum filing deadline of INA § 208(a)(2)(B)."),
]

FEATURE_NAMES = [name for name, _ in FEATURES]

OUT_COLUMNS = [
    "case_id", "pdf_url", "model", "feature",
    "predicted", "evidence", "latency_ms", "error",
]


def build_prompt() -> str:
    field_lines = []
    for name, defn in FEATURES:
        field_lines.append(f"  - {name}: {defn}")
    feature_block = "\n".join(field_lines)

    schema_lines = []
    for name, _ in FEATURES:
        schema_lines.append(f'  "{name}": true | false,')
        schema_lines.append(f'  "{name}_evidence": "<verbatim quote from the opinion, or \'Not mentioned in the opinion.\' if false>",')
    schema_block = "\n".join(schema_lines).rstrip(",")

    return (
        "You are a legal document analyst reading a Ninth Circuit asylum-related opinion.\n\n"
        "For each feature below, return a JSON boolean (true if the feature is present\n"
        "or applicable in the opinion, false if absent or not addressed) and a one-sentence\n"
        "verbatim evidence quote from the opinion. If false, the evidence value MUST be\n"
        "exactly the string \"Not mentioned in the opinion.\"\n\n"
        "FEATURES:\n"
        f"{feature_block}\n\n"
        "Return ONLY a JSON object with exactly these 20 keys and no other text:\n"
        "{\n"
        f"{schema_block}\n"
        "}\n\n"
        "RULES:\n"
        "- Each *_requested / *_finding / *_missed / *_actor / protected_ground_* / past_persecution_* field MUST be a JSON boolean.\n"
        "- Never return null. Never return strings for the boolean fields.\n"
        "- Quote evidence verbatim from the opinion. Do not paraphrase."
    )


PROMPT = build_prompt()


def _bool_field(name: str):
    """Build a Pydantic field annotation tuple (bool, ...)."""
    return (bool, ...)


# Dynamically construct the Pydantic model with the 20 fields
def build_model() -> type[BaseModel]:
    from pydantic import create_model
    fields: dict[str, tuple] = {}
    for name, _ in FEATURES:
        fields[name] = (bool, ...)
        fields[f"{name}_evidence"] = (str, "")
    return create_model("FeatureResult", **fields)  # type: ignore


FeatureResult = build_model()


def case_id_from_url(url: str) -> str:
    """Build a unique case id from a CA9 PDF URL.

    URLs look like .../opinions/2021/03/24/18-17274.pdf — the docket number alone
    is NOT unique (the same docket can have two opinions filed on different dates),
    so we suffix the filing date: 18-17274-2021-03-24.
    """
    parts = [p for p in url.split("/") if p]
    stem = Path(url).stem
    # The three path segments before the filename are YYYY/MM/DD.
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
    """Write all accumulated rows to OUT_CSV (atomic via temp file + rename)."""
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
    done = {
        (r["case_id"], r["model"])
        for r in rows
        if str(r.get("error", "")) == ""
    }
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

        # Which models still need this case?
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
                rows.extend(explode_to_rows(cid, url, model, None, None,
                                             f"pdf_download: {e}"))
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
                trues = sum(1 for n in FEATURE_NAMES if getattr(result, n))
                print(f"  {model:<55} -> {trues:>2}/10 True  ({lat} ms)")
                done.add((cid, model))
            else:
                print(f"  {model:<55} -> ERROR  ({lat} ms): {err[:80]}")

            # Drop any stale error rows for this (case, model) before re-adding
            rows = [r for r in rows if not (r["case_id"] == cid and r["model"] == model)]
            rows.extend(explode_to_rows(cid, url, model, result, lat, err))
            flush(rows)  # checkpoint after every model call

    out_df = pd.DataFrame(rows, columns=OUT_COLUMNS)
    print(f"\nWrote {len(out_df)} rows -> {OUT_CSV.relative_to(REPO_ROOT)}")

    # ── Summary ───────────────────────────────────────────────────────────────
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

    # Per-feature unanimous-agreement count across the 3 models
    print("\nPer-feature unanimous agreement (cases where all 3 models pick the same bool):")
    pv = out_df[out_df["error"] == ""].pivot_table(
        index=["case_id", "feature"], columns="model",
        values="predicted", aggfunc="first",
    )
    for feat in FEATURE_NAMES:
        if feat not in pv.index.get_level_values("feature"):
            continue
        sub = pv.xs(feat, level="feature")
        full = sub.dropna()
        n_agree = (full.nunique(axis=1) == 1).sum()
        print(f"  {feat:<45} {n_agree:>2}/{len(full)} unanimous")


if __name__ == "__main__":
    main()
