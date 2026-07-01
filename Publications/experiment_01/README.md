# Experiment 1 — LLM feature extraction vs. human gold standard

Probes 3 NVIDIA NIM models on **11 binary features** across the 30 curated Ninth Circuit
asylum opinions in [`reports/sample_30_cases.csv`](../../reports/sample_30_cases.csv), so
model output can be compared against a human-labeled gold standard.

## Contents

| File | Purpose |
|---|---|
| `extract_features.py` | Runs the 3 LLMs over the 30 cases; writes `results/features.csv` |
| `results/features.csv` | Long-format output (30 cases × 3 models × 11 features = 990 rows) |

The human gold-standard codebook lives in
[`../experiment_02/human_labeling_instructions.md`](../experiment_02/human_labeling_instructions.md).

## Models

- `meta/llama-3.3-70b-instruct`
- `deepseek-ai/deepseek-v4-flash`
- `mistralai/mistral-large-3-675b-instruct-2512`

## Features (11)

`asylum_requested`, `withholding_requested`, `CAT_requested`,
`protected_ground_political_opinion`, `protected_ground_particular_social_group`,
`past_persecution_physical_violence`, `past_persecution_death_threats`,
`persecutor_nongovernmental_actor`, `credibility_finding`,
`bars_one_year_deadline_missed`, **`nexus_requirement_met`** (new vs. the earlier
10-feature probe).

All 11 features are binary and recorded as `true`/`false` uniformly for both the
LLM and the human labelers.

## Run

```bash
set -a && source .env && set +a && source ninthc/bin/activate
python3 Publications/experiment_01/extract_features.py
```

The script checkpoints to `results/features.csv` after every `(case, model)` call and
resumes from it, so an interrupted run continues where it left off.

## Notes / open decisions

- **Definitions are identical** between the LLM (`extract_features.py`) and the human
  codebook (`../experiment_02/human_labeling_instructions.md`) — same 11 features, same
  wording, at the same altitude (surface "was it raised/present", not legal sufficiency).
