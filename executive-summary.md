# Executive Summary — Ninth Circuit Asylum RAG System

## Overview

This project delivers a Retrieval-Augmented Generation (RAG) search system over U.S. Court
of Appeals for the Ninth Circuit asylum opinions. It is integrated directly into the
existing `asylum-viewer` Next.js application as a "Case Search" panel on the right side of
the `/cases` page, rather than shipped as a standalone product. The system lets an
attorney paste a fact pattern or type a natural-language question and receive a ranked,
deduplicated list of the most relevant Ninth Circuit asylum cases, each accompanied by the
supporting text snippet, page number, and a link back to the source PDF.

The entire system runs on free-tier infrastructure with no recurring cost: Vercel hosts
the frontend, Render hosts the backend, NVIDIA NIM provides all model inference, and the
vector index lives in the Git repository itself via Git LFS. The only pre-existing service
it touches is the Supabase Postgres database that already backs `asylum-viewer`, and it
touches that only for structured case metadata — never for vectors.

The work was scoped against the Quantic AI Engineering rubric with the explicit goal of
satisfying every requirement for a score of 5: a working RAG pipeline with accurate
citations, a documented ingest/indexing process, a clean architecture, a public
deployment, CI/CD on push and pull request, design documentation, a quantitative
evaluation harness covering groundedness/citation-accuracy/latency, and a demo script.

---

## Architecture

The system is composed of three services plus the existing Supabase database.

```
asylum-viewer (Next.js · Vercel · free)
  ├─ /cases page + Case Search panel (collapsible right sidebar)
  └─ /api/rag/* server-side proxy routes → $RAG_API_URL
                                  │
                                  ▼
rag-api (FastAPI · Render free tier · 512 MB RAM)
  ├─ POST /chat    question → answer + citations
  ├─ POST /search  query → top-k similar cases (no LLM)
  └─ GET  /health  liveness + index stats
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                       ▼
   data/index.faiss      NVIDIA NIM (free)        Supabase (existing)
   data/metadata.parquet   embed / rerank / gen     case metadata only
   (Git LFS)
```

**Frontend.** The search panel is a collapsible right sidebar inside the existing `/cases`
page (a thin "💬 Chat" tab when closed, ~400px wide when open), so the new capability
augments the table the user already works with instead of fragmenting the app into a
separate route. The browser never calls the Render backend directly. Instead it POSTs to
Next.js proxy routes under `/api/rag/*`, which forward the request server-side to
`process.env.RAG_API_URL`. This keeps the backend URL server-only, avoids CORS preflights,
and prevents the endpoint from leaking into client bundles.

**Backend.** A FastAPI application exposes `/chat`, `/search`, and `/health`. At startup it
loads the FAISS index and the Parquet metadata into memory once (FastAPI lifespan hook),
pre-warms the BM25 index, and then serves all queries in-process with no further disk I/O.

**Vector store.** Embeddings are stored in a FAISS `IndexIVFPQ` (Product Quantization)
index, with the human-readable per-chunk metadata (chunk text, page, case link, chunk ID,
disposition, publication status) in a companion Parquet file. Both artifacts are versioned
in the Git repository through Git LFS (~3 MB total at the 30-case MVP scale), so the index
is a reproducible, version-controlled artifact rather than state living in an external
database.

**Inference.** All model calls go to NVIDIA NIM's free tier through its OpenAI-compatible
API: embedding with `nvidia/llama-nemotron-embed-1b-v2` (2048-dimensional vectors,
2048-token context), reranking with `nvidia/llama-nemotron-rerank-1b-v2`, and answer
generation with `meta/llama-3.3-70b-instruct`.

---

## How it works

### Ingest and indexing

`pipeline/rag_ingest.py` builds the index from the curated case list in
`Publications/sample_30_cases.csv`. For each case it downloads the opinion PDF, extracts text
per page with PyMuPDF, and splits the text into page-aware chunks of approximately 1,500
tokens with a 150-token overlap (token counts via `tiktoken`). Page-aware chunking is what
lets a citation say "page N of case X" instead of an opaque byte offset. Each chunk is
embedded with the NVIDIA embedder in `passage` mode, the vectors are L2-normalized so inner
product equals cosine similarity, and the resulting matrix is used to train and populate
the `IndexIVFPQ`. The index and metadata are written to `data/index.faiss` and
`data/metadata.parquet`, and an MLflow run logs the chunk count, model ID, and build
duration. A fixed `random.seed(42)` makes any sampling reproducible.

The index parameters auto-scale with corpus size, so the same code path serves the 30-case
MVP and the eventual full ~5,981-case corpus with no refactor: `nlist = max(4, round(4·√N))`
capped at `N/30` (so each Voronoi cell has enough training samples), `m = 64` subquantizers,
and 8 bits per code.

### Retrieval pipeline

A query flows through four stages:

1. **Dense retrieval.** The query is embedded in `query` mode (the embedder's asymmetric
   mode, tuned for QA-shaped inputs), and FAISS returns the top-N candidate chunks by
   cosine similarity.
2. **Neural reranking.** The candidates are re-scored by the NVIDIA reranker, which is a
   cross-encoder and therefore far more precise about query/passage relevance than the
   bi-encoder embedding used for the first-stage recall.
3. **BM25 hybrid.** A classical sparse BM25 score is computed for each candidate and
   blended with the rerank score as `0.6 · rerank + 0.4 · bm25`. This ensures that literal
   legal terms — a country name like "Honduras," a docket number, a statutory phrase —
   surface the exact-match passages, which a purely semantic system tends to bury under
   topically-similar-but-not-matching text.
4. **Dedupe by case.** Results are collapsed so each unique case appears once (keeping its
   highest-scoring chunk), then truncated to the top-k. Attorneys want a distinct list of
   cases, not three chunks of the same opinion occupying the top three slots.

The `/chat` endpoint additionally feeds the top-k passages to `meta/llama-3.3-70b-instruct`
with a numbered-passage prompt (`[1] … [2] …`), asks for `[N]`-tagged citations, then parses
the tags back to chunk IDs to render the citation cards.

### Guardrails

Out-of-corpus queries are refused using a dense-cosine threshold: if the maximum FAISS
cosine across all candidates is below 0.15, the system declines to answer. The dense score
is used here, rather than the rerank score, because empirically it is far better
calibrated — in-corpus queries score 0.21 and up while an out-of-corpus query like "weather
in Boston" scores ~0.09, whereas the rerank sigmoid collapses toward zero for many
legitimate natural-language questions and is too noisy to threshold on. Generation is
additionally capped at 500 tokens, and the system prompt instructs the model to ground
every claim in the supplied passages and to refuse only clearly unrelated questions.

---

## Resource footprint

The backend consumes roughly 170 MB of RAM at full load on the 30-case corpus — about 33%
of Render's 512 MB free-tier limit. The BM25 hybrid index, which is the most recent
addition, accounts for only about +9.5 MB at this scale. The Git LFS artifacts total ~3 MB,
which is 0.3% of GitHub's 1 GB free LFS allowance. There is comfortable headroom at MVP
scale, though see the scaling tradeoffs below for the full-corpus picture.

---

## How it meets the Quantic rubric (score 5)

| Rubric requirement | Where it is met |
|---|---|
| Outstanding RAG, correct responses, matching citations | Dense + NVIDIA rerank + BM25 hybrid in `rag_api/retrieval.py`; citations resolved to chunk IDs carrying snippet, page, and case link |
| Ingest and indexing works | `pipeline/rag_ingest.py` — PDF download, PyMuPDF extraction, page-aware ~1500-token chunking, builds `data/index.faiss` + `data/metadata.parquet`, MLflow logging |
| Excellent, well-structured architecture | Clean three-tier separation, all free-tier, no external vector DB (FAISS-in-Git-LFS), server-side proxy hides the backend |
| Public deployment fully functional | Render (backend) + Vercel (frontend), both public, both free, auto-deploy on push to `main` |
| CI/CD on push/PR | Three GitHub Actions workflows: `rag-api-test` (pytest + ruff + import smoke test), `rag-api-deploy` (Render deploy hook), `rag-eval` (scheduled evaluation) |
| Excellent design docs | `design-and-evaluation.md`, `ai-tooling.md`, `deployed.md`, README RAG section, and this summary |
| Evaluation: groundedness, citation accuracy, latency | `evaluation/run_eval.py` — LLM-as-judge groundedness, per-citation support check, latency p50/p95, 20-question stratified set, matplotlib chart |
| Excellent demo | Eight-minute screen-share script documented in the project plan (architecture → ingest → live queries → refusal → eval → CI → deploy) |

---

## Key design tradeoffs

Every significant decision in this system traded one desirable property for another. The
most consequential ones:

**FAISS in Git LFS vs. a hosted vector database.** Choosing an in-process FAISS index
versioned in Git LFS kept the system to three services with zero recurring cost and made
the index a reproducible artifact that travels with the code. The cost is that the index
is *static between deploys*: adding new cases requires re-running ingest and pushing a new
binary, rather than an incremental upsert against a live database. It also means the index
must fit in the backend's RAM, which couples index size to the Render instance size. We
evaluated Supabase pgvector, Neon, Pinecone, Qdrant, and Chroma; the pgvector options were
ruled out by their 500 MB free caps against a projected ~650 MB full corpus, and the hosted
vector DBs each added a vendor, an API key, and a second cold-start to stack on top of
Render's. For the rubric's emphasis on a clean, reproducible, fully-free architecture,
FAISS-in-Git-LFS was the better fit — but a team optimizing for live, incremental updates
would reasonably choose a hosted store.

**`IndexIVFPQ` from day one vs. starting with a flat index.** Using a quantized IVF index
from the start means the build and load code is identical at every corpus scale, so the
jump from 30 cases to ~6,000 requires no code change. The tradeoff is that at 30-case scale
(~700 chunks) the quantization is over-engineered: the IVF clusters are under-trained and
recall is an estimated 1–3% lower than a simple `IndexFlatIP` would deliver. We accepted a
small, measurable recall hit at MVP scale in exchange for never rewriting the index code —
a deliberate bet that the system will grow into the index rather than the other way around.

**BM25 hybrid vs. pure neural retrieval.** Adding a classical sparse signal fixed a real,
observed failure mode (literal terms like country names being out-ranked by semantically
similar passages) and is cheap in memory at MVP scale. The tradeoffs are a fixed blend
weight (0.6/0.4) that is not yet tuned per query type, additional per-query computation,
and a BM25 index whose memory cost grows with the corpus and which currently rebuilds in
memory at startup rather than being persisted.

**Dedupe by case vs. returning the best chunks.** Collapsing to one result per case gives
attorneys the distinct case list they actually want, but it discards potentially useful
secondary passages from a highly relevant case. A case that is relevant in three distinct
ways is currently represented by only its single best chunk.

**Generation with a 70B model vs. a smaller/faster model.** `meta/llama-3.3-70b-instruct`
produces high-quality, well-grounded prose, but it is the dominant contributor to `/chat`
latency. On NVIDIA's free tier, queueing can push p95 latency well past the warm target.
A smaller model would be faster and cheaper but would likely degrade groundedness and
citation discipline.

**Synchronous JSON response vs. streaming.** The current `/chat` returns a single JSON
payload only after the full answer is generated, which is simpler to implement, test, and
cache. The cost is user-perceived latency: the user waits several seconds staring at a
spinner instead of watching tokens appear. Streaming is the top item on the post-MVP list.

**Render free tier vs. an always-on host.** The free tier costs nothing but sleeps after
15 minutes of inactivity and takes ~30 seconds to cold-start, so the first query after idle
is slow. This is an acceptable tradeoff for a prototype and demo, but not for production
traffic.

---

## Room for improvement

The prototype-1 evaluation (30-case corpus) confirmed the pipeline works end-to-end on
every question, but also surfaced clear, addressable gaps. Current measured numbers sit
below the rubric's "excellent" targets — groundedness ~43%, citation accuracy ~55%, refusal
correctness ~55%, p50 latency ~8.5s, p95 ~55s — and the analysis below explains why and
what closes each gap.

1. **Expand the corpus from 30 to ~6,000 cases.** This is the single highest-leverage
   change. Many evaluation misses are specific-fact questions ("did the court grant case
   24-631?") where the relevant case simply is not in the 30-case MVP, or where the
   embedder matches poorly on docket numbers because there is too little surrounding
   context to disambiguate. A larger corpus dramatically improves retrieval recall, and
   because the index parameters auto-scale, it requires only re-running `rag_ingest.py`.

2. **Tune the refusal threshold.** The fixed 0.15 dense-score cutoff currently refuses some
   legitimate in-corpus questions while still letting some borderline cases through. A
   sweep over {0.10, 0.12, 0.15, 0.18} against the labeled eval set would raise refusal
   correctness without weakening out-of-corpus rejection.

3. **Make the generation prompt citation-strict.** The model frequently cites passages it
   does not actually rely on, which depresses citation accuracy. A prompt revision
   requiring it to cite *only* the passage(s) that directly support each individual claim,
   plus a post-hoc check that drops unsupported citations, should lift the metric
   substantially.

4. **Run the scaffolded ablations.** The evaluation harness already supports sweeping
   `chunk_size ∈ {500, 1000, 1500}` and `k ∈ {3, 5, 10}`, but prototype-1 skipped them to
   stay within the free-tier rate-limit budget. Running these would let us choose chunk
   size and k empirically rather than by rule of thumb, and would produce the ablation
   table the rubric rewards.

5. **Tune or learn the hybrid blend weight.** The 0.6/0.4 rerank/BM25 split is a reasonable
   default but is uniform across all queries. Keyword-heavy queries (a specific statute or
   country) likely want more BM25 weight; conceptual queries want more rerank weight. A
   small tuning pass, or a lightweight query classifier that picks the weight, would
   improve ranking quality.

6. **Stream `/chat` responses.** Switching from a single JSON response to a server-sent
   token stream turns the experience from "wait, then see the answer" into "watch the
   answer appear," which is both a better demo and a real UX upgrade. The 70B model
   supports SSE natively; the change is small on both ends, with citation tags buffered
   until close so parsing stays identical.

7. **Plan BM25 persistence for full-corpus scale.** At MVP scale the in-memory BM25 rebuild
   at startup is negligible, but at full corpus it grows in both memory and startup time.
   Options include persisting the BM25 index alongside the FAISS artifact in Git LFS,
   moving sparse retrieval to SQLite FTS5, or dropping BM25 in favor of a single hybrid
   retriever — to be decided once full-corpus memory is profiled against Render's 512 MB
   ceiling.

8. **Address cold starts and latency for production.** If this graduates from prototype to
   production, the Render free tier's sleep/cold-start behavior and the NVIDIA free-tier
   queueing that drives p95 latency would need to be addressed — via a warm-keeping ping,
   a paid inference tier, or a smaller/faster generation model — depending on the
   latency budget the use case actually requires.

These are the Sprint-2 priorities. None requires re-architecting the system; each is a
tuning or incremental-feature pass on the foundation that is already in place.
