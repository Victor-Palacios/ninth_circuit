# Experiment 2 — human labels

| File | Purpose |
|---|---|
| `Asylum_Experiment_2_noel.xlsx` | Noel's original labeling spreadsheet (raw, unedited) |
| `labels_noel.csv` | Noel's labels as CSV: `link`, the 11 features (`true`/`false`), a `<feature>_evidence` column after each, `time`, `notes` |
| `labels.csv` | Gold standard read by [`../../experiment_01/score.py`](../../experiment_01/score.py). Currently identical to `labels_noel.csv` (single labeler) |

Each additional labeler gets their own `labels_<name>.csv`; `labels.csv` holds the final adjudicated labels.
