"""Extract `asylum_requested` (boolean) + evidence quote from the 30 sample PDFs
using 3 free NVIDIA NIM models.

For each (case, model) we record:
  case_id, pdf_url, model, asylum_requested (bool), asylum_requested_evidence (str),
  latency_ms, error

The boolean answer is enforced by Pydantic. The evidence quote is a free-form
string (no constraints) per the user's spec.

Outputs:
  evaluation/results/nvidia_asylum_requested.csv

Env:
  NVIDIA_API_KEY — nvapi-... key (loaded from .env at repo root)

Usage:
  set -a && source .env && set +a && source ninthc/bin/activate \
    && python3 evaluation/nvidia_asylum_requested.py
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
OUT_CSV = REPO_ROOT / "evaluation" / "results" / "nvidia_asylum_requested.csv"

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

MODELS = [
    "meta/llama-3.3-70b-instruct",
    "deepseek-ai/deepseek-v4-flash",
    "mistralai/mistral-large-3-675b-instruct-2512",
]

PROMPT = """\
You are a legal document analyst reading a Ninth Circuit asylum-related opinion.

Decide whether the petitioner applied for ASYLUM relief in this case (as opposed
to only withholding of removal or CAT protection — those are separate forms of
relief). Asylum is the affirmative grant under 8 U.S.C. § 1158.

Return ONLY a JSON object with exactly these two keys and no other text:
{
  "asylum_requested": true | false,
  "asylum_requested_evidence": "<one short verbatim quote from the opinion that supports your answer; if false, write 'Not mentioned in the opinion.'>"
}

Rules:
- asylum_requested MUST be a JSON boolean (true or false), never a string, never null.
- Quote text verbatim from the opinion; do not paraphrase the evidence."""


class AsylumRequestedResult(BaseModel):
    asylum_requested: bool
    asylum_requested_evidence: str


def case_id_from_url(url: str) -> str:
    """Pull the docket number out of a CA9 PDF URL, e.g. .../21-70493.pdf -> 21-70493."""
    return Path(url).stem


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


def call_model(client: OpenAI, model: str, pdf_text: str) -> AsylumRequestedResult:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": f"{PROMPT}\n\nOPINION:\n{pdf_text}"},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = strip_fences(resp.choices[0].message.content or "")
    data = json.loads(raw)
    return AsylumRequestedResult.model_validate(data)


def main() -> None:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise SystemExit("NVIDIA_API_KEY is not set.")

    client = OpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)

    df = pd.read_csv(SAMPLE_CSV)
    cases = df[["link"]].to_dict("records")
    print(f"Loaded {len(cases)} cases from {SAMPLE_CSV.name}")
    print(f"Models: {', '.join(MODELS)}")

    pdf_cache: dict[str, str] = {}
    rows: list[dict] = []

    for i, row in enumerate(cases, 1):
        url = row["link"]
        cid = case_id_from_url(url)
        print(f"\n[{i}/{len(cases)}] {cid}")

        try:
            if url not in pdf_cache:
                pdf_cache[url] = extract_pdf_text(url)
            text = pdf_cache[url]
            print(f"  pdf chars: {len(text):,}")
        except Exception as e:
            print(f"  ERROR downloading PDF: {e}")
            for model in MODELS:
                rows.append({
                    "case_id": cid, "pdf_url": url, "model": model,
                    "asylum_requested": None, "asylum_requested_evidence": "",
                    "latency_ms": None, "error": f"pdf_download: {e}",
                })
            continue

        for model in MODELS:
            t0 = time.perf_counter()
            err = None
            result: AsylumRequestedResult | None = None
            try:
                result = call_model(client, model, text)
            except (json.JSONDecodeError, ValidationError) as e:
                err = f"parse: {type(e).__name__}: {e}"
            except Exception as e:
                err = f"api: {type(e).__name__}: {e}"
            latency_ms = int((time.perf_counter() - t0) * 1000)

            if result is not None:
                print(f"  {model:<55} -> {result.asylum_requested}  ({latency_ms} ms)")
                rows.append({
                    "case_id": cid, "pdf_url": url, "model": model,
                    "asylum_requested": result.asylum_requested,
                    "asylum_requested_evidence": result.asylum_requested_evidence,
                    "latency_ms": latency_ms, "error": "",
                })
            else:
                print(f"  {model:<55} -> ERROR  ({latency_ms} ms): {err}")
                rows.append({
                    "case_id": cid, "pdf_url": url, "model": model,
                    "asylum_requested": None, "asylum_requested_evidence": "",
                    "latency_ms": latency_ms, "error": err or "",
                })

    out_df = pd.DataFrame(rows, columns=[
        "case_id", "pdf_url", "model",
        "asylum_requested", "asylum_requested_evidence",
        "latency_ms", "error",
    ])
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote {len(out_df)} rows -> {OUT_CSV.relative_to(REPO_ROOT)}")

    # Summary by model
    print("\nSummary (non-error predictions):")
    for model in MODELS:
        sub = out_df[(out_df["model"] == model) & (out_df["error"] == "")]
        n_true = int((sub["asylum_requested"] == True).sum())
        n_false = int((sub["asylum_requested"] == False).sum())
        n_err = int(((out_df["model"] == model) & (out_df["error"] != "")).sum())
        print(f"  {model:<55} true={n_true:>3}  false={n_false:>3}  errors={n_err:>3}")


if __name__ == "__main__":
    main()
