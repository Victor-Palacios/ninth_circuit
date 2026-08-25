# Intern Projects — Ninth Circuit Asylum Pipeline

This repository runs a fully automated pipeline that reads every new opinion published by
the U.S. Court of Appeals for the Ninth Circuit, flags the ones involving asylum,
withholding of removal, or Convention Against Torture relief, and extracts 70+ structured
legal features from each — country of origin, protected grounds, persecutor identity,
credibility findings, statutory bars, final disposition — each paired with a verbatim
supporting quote. It has processed **5,779 asylum cases** so far, runs daily on GitHub
Actions, and costs **$0/month** because every model call goes to a free-tier LLM API. On
top of that corpus sits a public case browser and a retrieval-augmented (RAG) chat panel
that lets an attorney ask questions in plain English.

Two intern projects are open. They share the data and the infrastructure but are otherwise
independent — one is a measurement/research project ending in a paper, the other is a
retrieval-and-evaluation engineering project. Both are unfinished real work, not exercises:
the failing jobs, the unscored experiment, and the mediocre eval numbers described below
are the actual current state of the repo.

---

## Project 1 — Do language models read asylum law the way a human does?

*(pipeline maintenance + the extraction-validation study)*

Empirical research on immigration adjudication has always been bottlenecked on the same
step: someone has to read the opinions. Coding a few hundred decisions for "was a
credibility finding made?" or "did the court find the required nexus to a protected
ground?" is weeks of trained human labor, which is why most studies in this area are built
on small hand-coded samples. Large language models can obviously produce those labels in
seconds — the open question is whether the labels are *right*, which models are good enough,
and whether the model can be trusted on the legally subtle features rather than just the
easy bookkeeping ones. This project is the experiment that answers that, and the resulting
validation study is intended for publication.

The design is already in place. Eleven binary features are defined identically for the
machine and for the human (`Publications/experiment_02/human_labeling_instructions.md` is
the human codebook; the same wording is compiled into the model prompt from
`Publications/experiment_01/extract_features.py`). Thirty curated opinions, stratified
across published/unpublished and granted/denied/remanded, are run through a sweep of models
spanning three orders of magnitude in size — Llama 3.2 1B and 3B, Phi-4-mini, Llama 3.1 8B,
Llama 3.3 70B, Mistral Large 3 675B — each returning all 11 booleans plus an evidence quote
in one structured JSON call. Human labelers are coding the same 30 cases by hand to produce
the gold standard. Scoring is per model, per feature: accuracy, precision, recall, F1, and
Cohen's κ against the humans. Everything is tracked in git rather than an external service,
so the commit SHA on any results file pins the exact prompt and feature definitions that
produced those numbers.

Real findings are already visible in the raw output, waiting for someone to chase them
down. Structured-output reliability does not degrade monotonically with model size: Llama
3.2 **3B failed to emit parseable JSON on 19 of 30 calls, while the smaller 1B model failed
on 13** and 8B failed on none. The two frontier models agree on the easy features
(`credibility_finding`, 29/30) but disagree most on `asylum_requested` (25/30) — the single
most basic question in the entire codebook — which is either a prompt-definition problem or
a genuinely hard reading problem, and telling those apart is exactly the kind of question
the study exists to answer. And the same sweep recorded a mean latency of 351 seconds for
the 70B model against 13 seconds for the 675B one, which nobody has explained yet.

The other half of the job is keeping the machine that produces the data healthy, because a
paper about a pipeline is only as good as the pipeline. The daily fetch → classify →
extract jobs run unattended on GitHub Actions and they do break: extraction runs regularly
get cancelled at the 60-minute job timeout mid-batch, the weekly RAG evaluation has failed
5 of its last 6 scheduled runs (a single unretried `openai.APIConnectionError` in the judge
kills a 2h44m run and commits nothing), and the court's website is a scraping target that
changes without warning. You'd own that surface: make the jobs resilient, make their
failures visible, and make sure the numbers in the paper come from a pipeline that actually
ran.

**Good fit if you like:** experiment design and measurement, inter-rater reliability
statistics (κ, agreement, confidence intervals), working with LLM APIs and structured
output, practical Python/pandas, keeping automated systems alive, and writing up results
for a real audience.

**What already exists:** `Publications/experiment_01/` (sweep + scoring scripts, raw
results for six models), `Publications/experiment_01_tracking_plan.md` (the full
methodology), `Publications/experiment_02/` (human codebook), `pipeline/` (fetch, classify,
extract, QA), `.github/workflows/` (all the scheduled jobs).

**Where you'd start:**
1. Land the human gold standard as `Publications/experiment_02/results/labels.csv` and run
   `score.py` for the first time — today it degrades to prediction-only diagnostics because
   there is nothing to score against.
2. Add a second human labeler on an overlapping subset so we can report inter-annotator
   agreement alongside model-vs-human agreement. A model that matches humans as well as
   humans match each other is a much stronger claim.
3. Fix the JSON-parse failures in the small models (retry, repair, or constrained decoding)
   and report the failure rate *as a result* rather than hiding it — "how small can you go"
   is a headline finding.
4. Harden the daily jobs: retry/backoff around every model call, chunk the extraction batch
   so it finishes inside the timeout, and alert when a scheduled run fails instead of
   failing silently.
5. Once the 30-case validation holds up, scale the validated features across all 5,779
   cases and report prevalence with proper uncertainty.

---

## Project 2 — Making legal RAG trustworthy enough for an attorney

*(retrieval, evaluation, and the last mile to production)*

An immigration attorney with a client's fact pattern wants the same thing every time: which
Ninth Circuit cases look like this one, and what did the court actually say? That is a
retrieval problem with an unusually low tolerance for confident nonsense — a citation to a
case that does not say what the answer claims is worse than no answer at all. This repo has
a working RAG system aimed at that problem: FAISS dense retrieval over page-aware chunks,
an NVIDIA cross-encoder reranker, a BM25 sparse hybrid so literal terms like a country name
or a docket number are not buried by merely topical matches, deduplication to one result
per case, a refusal threshold for out-of-corpus questions, and Llama 3.3 70B generating
answers with `[N]`-tagged citations that resolve back to a specific page of a specific
opinion. It's deployed, it's public, and it evaluates itself every week.

It is also, by its own measurements, not good enough yet — which is the interesting part.
The most recent automated evaluation scored **40% groundedness, 67% citation accuracy, 95%
refusal accuracy, and a p50 latency of 52 seconds** (p95: 110 seconds). The corpus behind
those numbers is **30 cases out of 5,779**. The refusal threshold (0.15 dense cosine), the
hybrid blend weight (0.6 rerank / 0.4 BM25), the chunk size, and *k* were all set by
reasonable rule of thumb and have never been tuned against labeled data — the ablation
scaffolding exists in the eval harness but has never been run. Your project is to close
that gap and to prove you closed it, which means the evaluation itself is as much the
subject as the retriever: 20 questions scored by a single LLM judge cannot reliably detect
a five-point improvement, and validating the judge against human ratings is its own small
piece of research (and connects directly to Project 1's gold-standard work).

The engineering has real constraints, which is what makes it fun rather than a
hyperparameter grind. The whole system runs on free tiers: the backend has 512 MB of RAM
and sleeps after 15 minutes of inactivity, the vector index ships inside the git repo via
Git LFS, and a 200x corpus expansion has to fit in that memory budget — so scaling from 30
cases to the full corpus is a genuine design problem (persist BM25? move sparse retrieval
to SQLite FTS5? drop it?), not a re-run. Latency is the other honest failure: nobody waits
110 seconds for an answer, and switching `/chat` to a streamed response plus profiling
where the seconds actually go is the difference between a demo and a tool someone uses.

**Good fit if you like:** information retrieval and embeddings, evaluation methodology,
Python/FastAPI, a bit of Next.js on the frontend, and the systems-engineering puzzle of
making something real work inside a hard resource budget.

**What already exists:** `rag_api/` (retrieval, reranking, hybrid scoring, guardrails,
generation), `pipeline/rag_ingest.py` (PDF → page-aware chunks → FAISS index),
`evaluation/` (20-question set, LLM-judge harness, weekly workflow, historical results),
`asylum-viewer/` (Next.js chat panel + server-side proxy), and `design-and-evaluation.md` +
`executive-summary.md`, which document every design tradeoff and are candid about what is
weak.

**Where you'd start:**
1. Fix the weekly evaluation job so it stops dying on a transient API error and produces a
   trustworthy weekly time series — you cannot improve what you cannot measure.
2. Expand the eval set beyond 20 questions, add human ratings for a subset, and check
   whether the LLM judge actually agrees with people before trusting any of its verdicts.
3. Run the ablations that are already scaffolded: chunk size ∈ {500, 1000, 1500}, k ∈ {3, 5,
   10}, refusal threshold ∈ {0.10, 0.12, 0.15, 0.18}, hybrid α — and report them as a table.
4. Make citations strict: prompt the model to cite only what each claim rests on, then
   verify each citation post-hoc and drop the ones that don't hold up.
5. Scale the index from 30 cases toward the full corpus within the 512 MB ceiling, and
   measure what recall, latency, and memory actually do as N grows.
6. Stream `/chat` responses and attack p95 latency.

---

## Getting set up (either project)

```bash
python3 -m venv ninthc && source ninthc/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in NVIDIA_API_KEY, SUPABASE_URL, SUPABASE_SECRET_KEY
git lfs install && git lfs pull   # RAG project only: pulls data/index.faiss
```

Start with `README.md` for the pipeline, `design-and-evaluation.md` for the RAG system, and
`Publications/experiment_01_tracking_plan.md` for the study. `ai-tooling.md` describes how
AI tooling was used during development — with one hard exception that applies to Project 1:
the **human gold-standard labels must never be produced with the help of any LLM**, since
they are the measuring stick the entire study depends on.
