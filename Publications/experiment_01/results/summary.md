# Experiment 1 — sweep results

- **Scored:** 2026-07-09 00:43 UTC
- **Commit:** `215fae81e983` (this SHA pins the exact prompt + feature definitions)
- **Cases:** 30    **Models:** 3    **Gold standard:** NOT YET AVAILABLE


## Model health (per full sweep)

| model | calls | errors | error_rate | mean_latency_ms |
| --- | --- | --- | --- | --- |
| deepseek-ai/deepseek-v4-flash | 30 | 30 | 1.0 | 0 |
| meta/llama-3.3-70b-instruct | 30 | 9 | 0.3 | 372889 |
| mistralai/mistral-large-3-675b-instruct-2512 | 30 | 0 | 0.0 | 13433 |


## Prediction-only diagnostics (no gold standard yet)

The human gold standard (`Publications/experiment_02/results/labels.csv`) is not present, so accuracy/F1/kappa cannot be computed. Showing the per-feature true-rate for each model instead.

| model | feature | n | true_rate |
| --- | --- | --- | --- |
| meta/llama-3.3-70b-instruct | CAT_requested | 21 | 0.667 |
| meta/llama-3.3-70b-instruct | asylum_requested | 21 | 0.476 |
| meta/llama-3.3-70b-instruct | bars_one_year_deadline_missed | 21 | 0.048 |
| meta/llama-3.3-70b-instruct | credibility_finding | 21 | 0.286 |
| meta/llama-3.3-70b-instruct | nexus_requirement_met | 21 | 0.048 |
| meta/llama-3.3-70b-instruct | past_persecution_death_threats | 21 | 0.286 |
| meta/llama-3.3-70b-instruct | past_persecution_physical_violence | 21 | 0.429 |
| meta/llama-3.3-70b-instruct | persecutor_nongovernmental_actor | 21 | 0.429 |
| meta/llama-3.3-70b-instruct | protected_ground_particular_social_group | 21 | 0.286 |
| meta/llama-3.3-70b-instruct | protected_ground_political_opinion | 21 | 0.19 |
| meta/llama-3.3-70b-instruct | withholding_requested | 21 | 0.619 |
| mistralai/mistral-large-3-675b-instruct-2512 | CAT_requested | 30 | 0.667 |
| mistralai/mistral-large-3-675b-instruct-2512 | asylum_requested | 30 | 0.5 |
| mistralai/mistral-large-3-675b-instruct-2512 | bars_one_year_deadline_missed | 30 | 0.033 |
| mistralai/mistral-large-3-675b-instruct-2512 | credibility_finding | 30 | 0.3 |
| mistralai/mistral-large-3-675b-instruct-2512 | nexus_requirement_met | 30 | 0.033 |
| mistralai/mistral-large-3-675b-instruct-2512 | past_persecution_death_threats | 30 | 0.3 |
| mistralai/mistral-large-3-675b-instruct-2512 | past_persecution_physical_violence | 30 | 0.367 |
| mistralai/mistral-large-3-675b-instruct-2512 | persecutor_nongovernmental_actor | 30 | 0.467 |
| mistralai/mistral-large-3-675b-instruct-2512 | protected_ground_particular_social_group | 30 | 0.267 |
| mistralai/mistral-large-3-675b-instruct-2512 | protected_ground_political_opinion | 30 | 0.167 |
| mistralai/mistral-large-3-675b-instruct-2512 | withholding_requested | 30 | 0.6 |
