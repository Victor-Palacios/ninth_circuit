"""Evaluate the RAG system on the eval question set.

Metrics (rubric-required):
  - Groundedness:    LLM-as-judge — does the answer's content come from the citations?
  - Citation Accuracy: For each citation, does the snippet support the claim that cites it?
  - Latency p50/p95: from the /chat response's latency_ms field
  - Refusal correctness: out-of-corpus questions should be refused

Usage:
  python evaluation/run_eval.py --against http://localhost:8000
  python evaluation/run_eval.py --against https://rag-api-xxx.onrender.com

Outputs:
  evaluation/results/<date>.json
  evaluation/results/latest.json
  evaluation/results/latest.png  (matplotlib chart)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

import matplotlib.pyplot as plt  # type: ignore
import requests
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Modern, blue-focused chart style — matches docs/architecture.svg palette.
# White canvas, generous whitespace, no chartjunk, bold left-aligned titles,
# rounded end-of-bar value boxes (see write_chart).
INK = "#373737"      # primary text / dark series
ACCENT = "#30a2da"   # brand blue — the focus color
ACCENT_SOFT = "#9ecfe8"  # muted blue for below-target bars
CRIMSON = "#a50026"  # target threshold marker
MUTED = "#9a9a9a"    # secondary text

plt.rcParams.update({
    "figure.facecolor": "#ffffff",
    "axes.facecolor":   "#ffffff",
    "axes.edgecolor":   INK,
    "axes.labelcolor":  INK,
    "xtick.color":      INK,
    "ytick.color":      INK,
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.spines.left":   False,
    "axes.spines.bottom": False,
    "axes.grid": False,
    "font.family": "DejaVu Sans",
    "font.size": 13,
})

JUDGE_MODEL = "meta/llama-3.3-70b-instruct"
NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

EVAL_DIR = Path(__file__).resolve().parent
QUESTIONS_PATH = EVAL_DIR / "eval_questions.json"
RESULTS_DIR = EVAL_DIR / "results"


def _judge_client() -> OpenAI:
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY env var required for LLM-as-judge.")
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=key)


def _judge_call(prompt: str, max_tokens: int) -> str:
    """Call the judge LLM with exponential backoff on 429s."""
    import openai as _openai
    delays = [2, 5, 15, 30, 60]
    for attempt, delay in enumerate(delays + [None]):
        try:
            resp = _judge_client().chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except _openai.RateLimitError:
            if delay is None:
                raise
            print(f"    rate-limited, sleeping {delay}s (attempt {attempt + 1})…")
            time.sleep(delay)
    return ""  # unreachable


def judge_groundedness(answer: str, snippets: list[str]) -> bool:
    """Ask the judge: is EVERY claim in the answer supported by the snippets? YES/NO."""
    if not answer.strip():
        return False
    if not snippets:
        return False
    ctx = "\n\n".join(f"[{i+1}] {s}" for i, s in enumerate(snippets))
    prompt = (
        "You are a strict fact-checker. Given an ANSWER and the SOURCE PASSAGES it was "
        "supposedly drawn from, decide if EVERY factual claim in the ANSWER is supported "
        "by the SOURCE PASSAGES. Respond with exactly YES or NO, then a brief reason.\n\n"
        f"SOURCE PASSAGES:\n{ctx}\n\nANSWER:\n{answer}\n\nResponse:"
    )
    return _judge_call(prompt, max_tokens=120).upper().startswith("YES")


def judge_citation_supports(answer: str, snippet: str) -> bool:
    """Does this one snippet support the claims in the answer it's cited for? YES/NO."""
    prompt = (
        "Does the SNIPPET below substantively support the ANSWER? Reply with exactly YES or NO.\n\n"
        f"SNIPPET:\n{snippet}\n\nANSWER:\n{answer}\n\nReply:"
    )
    return _judge_call(prompt, max_tokens=10).upper().startswith("YES")


def call_chat(base_url: str, question: str, k: int = 5, timeout: int = 90) -> dict:
    resp = requests.post(
        f"{base_url}/chat",
        json={"question": question, "k": k},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def warm_service(base_url: str) -> None:
    """Wake up a cold Render container before we start timing."""
    print(f"Warming {base_url}/health …", end=" ", flush=True)
    t0 = time.perf_counter()
    try:
        r = requests.get(f"{base_url}/health", timeout=60)
        elapsed = time.perf_counter() - t0
        print(f"{r.status_code} in {elapsed:.1f}s")
    except Exception as e:
        print(f"⚠️  health check failed: {e}")


def run(base_url: str) -> dict:
    questions = json.loads(QUESTIONS_PATH.read_text())["questions"]
    print(f"Loaded {len(questions)} eval questions.\n")

    warm_service(base_url)

    per_question: list[dict] = []
    latencies: list[int] = []

    for i, q in enumerate(questions):
        if i > 0:
            time.sleep(4)  # be polite to NVIDIA free-tier rate limit
        print(f"[{q['id']}] {q['question']}")
        t0 = time.perf_counter()
        try:
            resp = call_chat(base_url, q["question"], k=5)
        except Exception as e:
            print(f"  ⚠️  API error: {e}")
            per_question.append({**q, "error": str(e)})
            continue
        wall_ms = int((time.perf_counter() - t0) * 1000)

        answer = resp.get("answer", "")
        refused = resp.get("refused", False)
        citations = resp.get("citations", [])
        snippets = [c["snippet"] for c in citations]

        # ── Refusal correctness ─────────────────────────────────────────────
        refusal_ok = refused == q["expect_refuse"]

        # ── Groundedness + citation accuracy (skip if refused) ──────────────
        if refused:
            groundedness = None
            cite_correct = None
        else:
            groundedness = judge_groundedness(answer, snippets)
            if citations:
                results = [judge_citation_supports(answer, s) for s in snippets]
                cite_correct = sum(results) / len(results)
            else:
                cite_correct = 0.0  # answer had no citations — automatic 0

        latencies.append(resp.get("latency_ms", wall_ms))

        per_question.append({
            **q,
            "answer": answer,
            "refused": refused,
            "refusal_ok": refusal_ok,
            "groundedness": groundedness,
            "citation_accuracy": cite_correct,
            "n_citations": len(citations),
            "latency_ms": resp.get("latency_ms", wall_ms),
            "wall_ms": wall_ms,
        })

        flag = "✓" if refusal_ok else "✗"
        g_str = "—" if groundedness is None else ("Y" if groundedness else "N")
        c_str = "—" if cite_correct is None else f"{cite_correct:.2f}"
        print(f"  refused={refused} ok={flag}  groundedness={g_str}  cite_acc={c_str}  "
              f"latency={resp.get('latency_ms')}ms")

    # ── Aggregate ────────────────────────────────────────────────────────────
    grounded = [r for r in per_question if r.get("groundedness") is not None]
    cited = [r for r in per_question if r.get("citation_accuracy") is not None]
    refusal = per_question

    summary = {
        "n_questions":       len(per_question),
        "groundedness_pct":  (sum(1 for r in grounded if r["groundedness"]) / len(grounded)) if grounded else 0.0,
        "citation_acc_avg":  (sum(r["citation_accuracy"] for r in cited) / len(cited)) if cited else 0.0,
        "refusal_acc_pct":   sum(1 for r in refusal if r.get("refusal_ok")) / len(refusal),
        "latency_p50_ms":    int(statistics.median(latencies)) if latencies else 0,
        "latency_p95_ms":    int(statistics.quantiles(latencies, n=20)[-1]) if len(latencies) >= 5 else 0,
        "latency_mean_ms":   int(statistics.mean(latencies)) if latencies else 0,
        "n_in_corpus_eval":  len(grounded),
        "n_out_of_corpus":   sum(1 for q in questions if q["expect_refuse"]),
        "evaluated_at_utc":  datetime.now(timezone.utc).isoformat(),
        "rag_url":           base_url,
    }

    result = {"summary": summary, "questions": per_question}
    return result


def _value_box(ax, x, y, text, color, *, ha="left", va="center"):
    """Rounded, outlined value label — the end-of-line tag style from the design ref."""
    ax.annotate(
        text, (x, y), ha=ha, va=va, fontsize=13, fontweight="bold", color=color,
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=color, lw=2.0),
        annotation_clip=False, zorder=6,
    )


def write_chart(summary: dict, path: Path) -> None:
    """Two-panel evaluation dashboard, modern blue-focused style.

    Left: quality + guardrail percentages as horizontal bars with a target
    line. Right: latency percentiles. Both use rounded end-of-bar value boxes.
    """
    QUALITY_TARGET = 85  # % target for the "excellent" rubric band

    fig, (ax_q, ax_l) = plt.subplots(
        1, 2, figsize=(13.5, 5.6), gridspec_kw={"width_ratios": [1.65, 1]}
    )
    fig.patch.set_facecolor("#ffffff")

    # Bold, left-aligned figure title (anchored to the left panel's x=0)
    fig.suptitle(
        "RAG Evaluation — Quality, Guardrails & Latency",
        x=0.07, y=0.97, ha="left", fontsize=20, fontweight="bold", color=INK,
    )
    fig.text(
        0.07, 0.905,
        f"{summary['n_questions']}-question set · "
        f"{summary['n_in_corpus_eval']} in-corpus · evaluated {summary['evaluated_at_utc'][:10]}",
        ha="left", fontsize=12, color=MUTED,
    )

    # ── Panel 1: quality + guardrails (horizontal bars, top→bottom) ────────────
    metrics = [
        ("Groundedness",        summary["groundedness_pct"] * 100),
        ("Citation accuracy",   summary["citation_acc_avg"] * 100),
        ("Refusal correctness", summary["refusal_acc_pct"] * 100),
    ]
    labels = [m[0] for m in metrics]
    vals = [m[1] for m in metrics]
    y = list(range(len(metrics)))[::-1]  # first metric on top

    # faint track behind each bar for a polished, dashboard feel
    ax_q.barh(y, [100] * len(vals), height=0.5, color="#eef1f3", zorder=1)
    colors = [ACCENT if v >= QUALITY_TARGET else ACCENT_SOFT for v in vals]
    ax_q.barh(y, vals, height=0.5, color=colors, zorder=2)

    # target line + tag
    ax_q.axvline(QUALITY_TARGET, color=CRIMSON, linestyle=(0, (4, 3)), linewidth=1.8, zorder=3)
    ax_q.annotate(
        f"target {QUALITY_TARGET}%", (QUALITY_TARGET, len(metrics) - 0.34),
        ha="center", va="bottom", fontsize=11, fontweight="bold", color=CRIMSON,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none"),
        annotation_clip=False, zorder=5,
    )

    for yi, v, c in zip(y, vals, colors):
        box_c = ACCENT if v >= QUALITY_TARGET else CRIMSON
        _value_box(ax_q, min(v + 2, 99), yi, f"{v:.0f}%", box_c)

    ax_q.set_xlim(0, 112)
    ax_q.set_ylim(-0.6, len(metrics) - 0.3)
    ax_q.set_yticks(y)
    ax_q.set_yticklabels(labels, fontsize=14, fontweight="bold", color=INK)
    ax_q.set_xticks([])
    ax_q.tick_params(left=False, bottom=False)
    ax_q.set_title("Answer quality & guardrails", loc="left",
                   fontsize=14, fontweight="bold", color=INK, pad=14)

    # ── Panel 2: latency percentiles ───────────────────────────────────────────
    lat = [("p50", summary["latency_p50_ms"]), ("p95", summary["latency_p95_ms"])]
    llabels = [f"{name}" for name, _ in lat]
    lvals = [v for _, v in lat]
    ly = [1, 0]
    lmax = max(lvals + [1])

    ax_l.barh(ly, lvals, height=0.42, color=ACCENT, zorder=2)
    for yi, v in zip(ly, lvals):
        secs = v / 1000
        _value_box(ax_l, v + lmax * 0.02, yi, f"{secs:.1f}s", ACCENT)

    ax_l.set_xlim(0, lmax * 1.28)
    ax_l.set_ylim(-0.55, 1.55)
    ax_l.set_yticks(ly)
    ax_l.set_yticklabels(llabels, fontsize=14, fontweight="bold", color=INK)
    ax_l.set_xticks([])
    ax_l.tick_params(left=False, bottom=False)
    ax_l.set_title("Latency per /chat", loc="left",
                   fontsize=14, fontweight="bold", color=INK, pad=14)

    fig.subplots_adjust(left=0.205, right=0.965, top=0.80, bottom=0.08, wspace=0.42)
    plt.savefig(path, dpi=160, facecolor="#ffffff")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--against", default=os.environ.get("RAG_API_URL", "http://localhost:8000"),
                        help="Base URL of the RAG API (default: RAG_API_URL env or http://localhost:8000)")
    args = parser.parse_args()
    base = args.against.rstrip("/")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = run(base)

    s = result["summary"]
    print("\n=== SUMMARY ===")
    print(f"  Groundedness:        {s['groundedness_pct'] * 100:.1f}% over {s['n_in_corpus_eval']} in-corpus answers")
    print(f"  Citation accuracy:   {s['citation_acc_avg'] * 100:.1f}% (avg per-citation support)")
    print(f"  Refusal correctness: {s['refusal_acc_pct'] * 100:.1f}%")
    print(f"  Latency p50/p95:     {s['latency_p50_ms']} / {s['latency_p95_ms']} ms")

    # Write outputs
    date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dated_path = RESULTS_DIR / f"{date_stamp}.json"
    dated_path.write_text(json.dumps(result, indent=2))
    (RESULTS_DIR / "latest.json").write_text(json.dumps(result, indent=2))
    write_chart(s, RESULTS_DIR / "latest.png")

    print("\nWrote:")
    print(f"  {dated_path}")
    print(f"  {RESULTS_DIR / 'latest.json'}")
    print(f"  {RESULTS_DIR / 'latest.png'}")


if __name__ == "__main__":
    main()
