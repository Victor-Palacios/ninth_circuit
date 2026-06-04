"""Ingest asylum case PDFs into a FAISS index + Parquet metadata table for RAG.

Reads a CSV of case links (default: reports/sample_30_cases.csv), downloads each PDF,
extracts text page-by-page with PyMuPDF, chunks page-aware (~1500 tokens, 150 overlap),
embeds via NVIDIA NIM (nvidia/llama-3.2-nv-embedqa-1b-v2 — 2048-dim, 2048-token context),
builds a FAISS IndexIVFPQ from day 1 so the build/load code is identical at every scale,
and writes:
    data/index.faiss
    data/metadata.parquet

Env vars required:
    NVIDIA_API_KEY     — free-tier NVIDIA NIM key (nvapi-...)
    NVIDIA_BASE_URL    — defaults to https://integrate.api.nvidia.com/v1

Usage:
    python pipeline/rag_ingest.py --source reports/sample_30_cases.csv

Reproducibility: random.seed(42).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass

import faiss  # type: ignore
import numpy as np
import pandas as pd
import requests
import tiktoken
from openai import OpenAI

# mlflow and pymupdf are only needed by the CLI entrypoint, not by the pure
# helpers that unit tests exercise. Imported lazily inside the functions that
# use them so test environments don't need to install them.

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Constants ────────────────────────────────────────────────────────────────

EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"  # successor to llama-3.2-nv-embedqa-1b-v2 (EOL 2026-05-18); same 1B Llama base, 2048-dim
EMBED_DIM = 2048
EMBED_BATCH = 16  # NVIDIA NIM rate-limit friendly
PQ_SUBQUANTIZERS = 64  # 2048 / 64 = 32 dims per subquantizer; valid divisor
PQ_NBITS = 8
CHUNK_TOKENS = 1500
CHUNK_OVERLAP = 150
NVIDIA_BASE_URL_DEFAULT = "https://integrate.api.nvidia.com/v1"
SEED = 42

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INDEX_PATH = DATA_DIR / "index.faiss"
META_PATH = DATA_DIR / "metadata.parquet"


# ── Helpers ──────────────────────────────────────────────────────────────────

def download_pdf(url: str, timeout: int = 120) -> bytes:
    """Download a PDF into memory; raises on HTTP error."""
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def extract_pages(pdf_bytes: bytes) -> list[str]:
    """Return a list[str] with one element per page."""
    import pymupdf  # lazy: only needed by the CLI ingest path, not by tests
    pages: list[str] = []
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return pages


def chunk_page(
    text: str,
    encoder: tiktoken.Encoding,
    tokens_per_chunk: int = CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[str, int, int, int]]:
    """Split one page of text into ~tokens_per_chunk-token chunks with overlap.

    Returns list of (chunk_text, char_start, char_end, n_tokens).
    Chunks do NOT span pages — call once per page.
    """
    text = (text or "").strip()
    if not text:
        return []

    tokens = encoder.encode(text)
    if len(tokens) <= tokens_per_chunk:
        return [(text, 0, len(text), len(tokens))]

    chunks: list[tuple[str, int, int, int]] = []
    step = max(1, tokens_per_chunk - overlap)
    for i in range(0, len(tokens), step):
        sub_tokens = tokens[i : i + tokens_per_chunk]
        if not sub_tokens:
            break
        chunk_text = encoder.decode(sub_tokens)
        char_start = len(encoder.decode(tokens[:i]))
        char_end = char_start + len(chunk_text)
        chunks.append((chunk_text, char_start, char_end, len(sub_tokens)))
        if i + tokens_per_chunk >= len(tokens):
            break
    return chunks


def make_embed_client() -> OpenAI:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set. Add it to .env.")
    base_url = os.environ.get("NVIDIA_BASE_URL", NVIDIA_BASE_URL_DEFAULT)
    return OpenAI(base_url=base_url, api_key=api_key)


def embed_batch(client: OpenAI, texts: list[str], input_type: str = "passage") -> np.ndarray:
    """Embed a list of texts via NVIDIA NIM. Returns (N, EMBED_DIM) float32."""
    resp = client.embeddings.create(
        model=EMBED_MODEL,
        input=texts,
        encoding_format="float",
        extra_body={"input_type": input_type, "truncate": "END"},
    )
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    if vecs.shape[1] != EMBED_DIM:
        raise RuntimeError(
            f"Expected {EMBED_DIM}-dim embeddings from {EMBED_MODEL}, got {vecs.shape[1]}."
        )
    return vecs


def l2_normalize(vecs: np.ndarray) -> np.ndarray:
    """L2-normalize so inner-product == cosine similarity."""
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return (vecs / norms).astype(np.float32)


def compute_nlist(n_vectors: int) -> int:
    """Auto-scale IVF nlist with corpus size.

    Rule of thumb: nlist ≈ 4 * sqrt(N), capped so we have ~30 training samples per cell.
    Floors at 4.
    """
    target = round(4 * (n_vectors ** 0.5))
    max_safe = max(4, n_vectors // 30)
    return max(4, min(target, max_safe))


def build_index(vectors: np.ndarray) -> faiss.Index:
    """Build IndexIVFPQ (used at every scale per plan)."""
    n = vectors.shape[0]
    nlist = compute_nlist(n)
    print(f"  nlist={nlist}  (corpus N={n}, target ~30 samples/cell)")
    quantizer = faiss.IndexFlatIP(EMBED_DIM)
    index = faiss.IndexIVFPQ(
        quantizer, EMBED_DIM, nlist, PQ_SUBQUANTIZERS, PQ_NBITS, faiss.METRIC_INNER_PRODUCT
    )
    index.train(vectors)
    index.add(vectors)
    index.nprobe = max(1, nlist // 4)  # search ~25% of cells; good recall/speed tradeoff
    return index


# ── Main ──────────────────────────────────────────────────────────────────────

def run(source_csv: Path) -> dict:
    """Ingest case links from a CSV into FAISS + Parquet. Returns summary stats."""
    random.seed(SEED)
    np.random.seed(SEED)

    if not source_csv.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_csv}")

    sources = pd.read_csv(source_csv)
    if "link" not in sources.columns:
        raise ValueError(f"{source_csv} must have a 'link' column")

    print(f"Loaded {len(sources)} case links from {source_csv}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    encoder = tiktoken.get_encoding("cl100k_base")
    client = make_embed_client()

    # ── 1. Download + chunk ──────────────────────────────────────────────────
    rows: list[dict] = []
    failures: list[tuple[str, str]] = []
    t0 = time.perf_counter()
    for case_i, src in sources.iterrows():
        link = src["link"]
        print(f"[{case_i+1}/{len(sources)}] {link}")
        try:
            pdf_bytes = download_pdf(link)
            pages = extract_pages(pdf_bytes)
        except Exception as e:
            print(f"  ⚠️  download/extract failed: {e}")
            failures.append((link, str(e)))
            continue

        chunk_idx = 0
        for page_num, page_text in enumerate(pages, start=1):
            for chunk_text, char_start, char_end, n_tokens in chunk_page(page_text, encoder):
                rows.append({
                    "case_link":         link,
                    "chunk_idx":         chunk_idx,
                    "page":              page_num,
                    "char_start":        char_start,
                    "char_end":          char_end,
                    "text":              chunk_text,
                    "n_tokens":          n_tokens,
                    "case_pub_status":   src.get("pub_status", ""),
                    "case_disposition":  src.get("final_disposition", ""),
                    "case_char_count":   int(src.get("char_count", 0) or 0),
                })
                chunk_idx += 1

    download_seconds = time.perf_counter() - t0
    if not rows:
        raise RuntimeError("No chunks produced — check your source CSV and network.")
    print(f"\n  → {len(rows)} chunks across {len(sources) - len(failures)} cases "
          f"({download_seconds:.1f}s download+extract)")

    # ── 2. Embed in batches ──────────────────────────────────────────────────
    print(f"\nEmbedding {len(rows)} chunks via {EMBED_MODEL} (batch={EMBED_BATCH})…")
    t0 = time.perf_counter()
    all_vecs: list[np.ndarray] = []
    for i in range(0, len(rows), EMBED_BATCH):
        batch_texts = [r["text"] for r in rows[i : i + EMBED_BATCH]]
        vecs = embed_batch(client, batch_texts, input_type="passage")
        all_vecs.append(vecs)
        if (i // EMBED_BATCH) % 5 == 0:
            done = min(i + EMBED_BATCH, len(rows))
            print(f"  embedded {done}/{len(rows)}")
    vectors = np.vstack(all_vecs)
    vectors = l2_normalize(vectors)
    embed_seconds = time.perf_counter() - t0
    print(f"  → {vectors.shape} in {embed_seconds:.1f}s")

    # ── 3. Build FAISS index (IVFPQ from day 1) ──────────────────────────────
    print("\nBuilding FAISS IndexIVFPQ…")
    t0 = time.perf_counter()
    index = build_index(vectors)
    build_seconds = time.perf_counter() - t0
    print(f"  → ntotal={index.ntotal} in {build_seconds:.1f}s")

    # ── 4. Persist ───────────────────────────────────────────────────────────
    faiss.write_index(index, str(INDEX_PATH))

    # Assign chunk_id = FAISS row index (0..N-1, matches insertion order)
    meta_df = pd.DataFrame(rows)
    meta_df.insert(0, "chunk_id", np.arange(len(meta_df), dtype=np.int64))
    meta_df.to_parquet(META_PATH, compression="snappy", index=False)

    print("\nWrote:")
    print(f"  {INDEX_PATH}  ({INDEX_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"  {META_PATH}   ({META_PATH.stat().st_size / 1024:.1f} KB)")

    if failures:
        print(f"\n⚠️  {len(failures)} case(s) failed:")
        for link, err in failures:
            print(f"   - {link}: {err}")

    return {
        "n_cases":          int(len(sources) - len(failures)),
        "n_failures":       int(len(failures)),
        "n_chunks":         int(len(rows)),
        "download_seconds": round(download_seconds, 1),
        "embed_seconds":    round(embed_seconds, 1),
        "build_seconds":    round(build_seconds, 1),
        "index_size_kb":    round(INDEX_PATH.stat().st_size / 1024, 1),
        "meta_size_kb":     round(META_PATH.stat().st_size / 1024, 1),
        "nlist":            compute_nlist(len(rows)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "reports" / "sample_30_cases.csv",
        help="CSV of case links to ingest (must have a 'link' column)",
    )
    args = parser.parse_args()

    # MLflow is optional. It's imported lazily so unit tests don't need it, and
    # the whole experiment-logging block is skipped gracefully if the package
    # isn't installed — the ingest itself never depends on mlflow.
    try:
        import mlflow  # type: ignore
    except ImportError:
        mlflow = None
        print("mlflow not installed — running ingest without experiment logging.")

    if mlflow is None:
        run(args.source)
    else:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            mlflow.set_tracking_uri(db_url)
        mlflow.set_experiment("rag_ingest")

        with mlflow.start_run():
            mlflow.log_param("embed_model", EMBED_MODEL)
            mlflow.log_param("embed_dim", EMBED_DIM)
            mlflow.log_param("chunk_tokens", CHUNK_TOKENS)
            mlflow.log_param("chunk_overlap", CHUNK_OVERLAP)
            mlflow.log_param("pq_subquantizers", PQ_SUBQUANTIZERS)
            mlflow.log_param("pq_nbits", PQ_NBITS)
            mlflow.log_param("source", str(args.source))
            mlflow.log_param("seed", SEED)

            stats = run(args.source)

            for k, v in stats.items():
                mlflow.log_metric(k, v) if isinstance(v, (int, float)) else mlflow.log_param(k, v)

    print("\nDone. Next: git add data/ && git commit -m 'rag: ingest' && git push")


if __name__ == "__main__":
    main()
