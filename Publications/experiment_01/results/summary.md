# Experiment 1 — sweep results

- **Scored:** 2026-10-09 21:43 UTC
- **Commit:** `08b4df50822f` (this SHA pins the exact prompt + feature definitions)
- **Cases:** 30    **Models:** 2    **Gold standard:** present


## Model health (per full sweep)

| model | calls | errors | error_rate | mean_latency_ms |
| --- | --- | --- | --- | --- |
| meta/llama-3.3-70b-instruct | 30 | 0 | 0.0 | 351243 |
| mistralai/mistral-large-3-675b-instruct-2512 | 30 | 0 | 0.0 | 13433 |


## Accuracy vs. human gold standard (per model × feature)

| model | feature | n | tp | fp | fn | tn | accuracy | precision | recall | f1 | cohen_kappa |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| meta/llama-3.3-70b-instruct | CAT_requested | 30 | 18 | 4 | 1 | 7 | 0.833 | 0.818 | 0.947 | 0.878 | 0.619 |
| meta/llama-3.3-70b-instruct | asylum_requested | 30 | 13 | 5 | 2 | 10 | 0.767 | 0.722 | 0.867 | 0.788 | 0.533 |
| meta/llama-3.3-70b-instruct | bars_one_year_deadline_missed | 30 | 0 | 2 | 0 | 28 | 0.933 | 0.0 | 0.0 | 0.0 | 0.0 |
| meta/llama-3.3-70b-instruct | credibility_finding | 30 | 3 | 7 | 0 | 20 | 0.767 | 0.3 | 1.0 | 0.462 | 0.364 |
| meta/llama-3.3-70b-instruct | nexus_requirement_met | 30 | 0 | 3 | 1 | 26 | 0.867 | 0.0 | 0.0 | 0.0 | -0.053 |
| meta/llama-3.3-70b-instruct | past_persecution_death_threats | 30 | 7 | 2 | 1 | 20 | 0.9 | 0.778 | 0.875 | 0.824 | 0.754 |
| meta/llama-3.3-70b-instruct | past_persecution_physical_violence | 30 | 9 | 4 | 0 | 17 | 0.867 | 0.692 | 1.0 | 0.818 | 0.718 |
| meta/llama-3.3-70b-instruct | persecutor_nongovernmental_actor | 30 | 13 | 2 | 0 | 15 | 0.933 | 0.867 | 1.0 | 0.929 | 0.867 |
| meta/llama-3.3-70b-instruct | protected_ground_particular_social_group | 30 | 6 | 4 | 4 | 16 | 0.733 | 0.6 | 0.6 | 0.6 | 0.4 |
| meta/llama-3.3-70b-instruct | protected_ground_political_opinion | 30 | 5 | 3 | 1 | 21 | 0.867 | 0.625 | 0.833 | 0.714 | 0.63 |
| meta/llama-3.3-70b-instruct | withholding_requested | 30 | 16 | 5 | 1 | 8 | 0.8 | 0.762 | 0.941 | 0.842 | 0.577 |
| mistralai/mistral-large-3-675b-instruct-2512 | CAT_requested | 30 | 18 | 2 | 1 | 9 | 0.9 | 0.9 | 0.947 | 0.923 | 0.78 |
| mistralai/mistral-large-3-675b-instruct-2512 | asylum_requested | 30 | 13 | 2 | 2 | 13 | 0.867 | 0.867 | 0.867 | 0.867 | 0.733 |
| mistralai/mistral-large-3-675b-instruct-2512 | bars_one_year_deadline_missed | 30 | 0 | 1 | 0 | 29 | 0.967 | 0.0 | 0.0 | 0.0 | 0.0 |
| mistralai/mistral-large-3-675b-instruct-2512 | credibility_finding | 30 | 3 | 6 | 0 | 21 | 0.8 | 0.333 | 1.0 | 0.5 | 0.412 |
| mistralai/mistral-large-3-675b-instruct-2512 | nexus_requirement_met | 30 | 1 | 0 | 0 | 29 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| mistralai/mistral-large-3-675b-instruct-2512 | past_persecution_death_threats | 30 | 7 | 2 | 1 | 20 | 0.9 | 0.778 | 0.875 | 0.824 | 0.754 |
| mistralai/mistral-large-3-675b-instruct-2512 | past_persecution_physical_violence | 30 | 9 | 2 | 0 | 19 | 0.933 | 0.818 | 1.0 | 0.9 | 0.851 |
| mistralai/mistral-large-3-675b-instruct-2512 | persecutor_nongovernmental_actor | 30 | 12 | 2 | 1 | 15 | 0.9 | 0.857 | 0.923 | 0.889 | 0.798 |
| mistralai/mistral-large-3-675b-instruct-2512 | protected_ground_particular_social_group | 30 | 7 | 1 | 3 | 19 | 0.867 | 0.875 | 0.7 | 0.778 | 0.684 |
| mistralai/mistral-large-3-675b-instruct-2512 | protected_ground_political_opinion | 30 | 5 | 0 | 1 | 24 | 0.967 | 1.0 | 0.833 | 0.909 | 0.889 |
| mistralai/mistral-large-3-675b-instruct-2512 | withholding_requested | 30 | 15 | 3 | 2 | 10 | 0.833 | 0.833 | 0.882 | 0.857 | 0.658 |


## Per-model macro averages

| model | macro_accuracy | macro_f1 | macro_kappa |
| --- | --- | --- | --- |
| meta/llama-3.3-70b-instruct | 0.842 | 0.623 | 0.492 |
| mistralai/mistral-large-3-675b-instruct-2512 | 0.903 | 0.768 | 0.687 |
