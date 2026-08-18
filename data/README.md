# Research Data

This directory contains datasets used by the 5G RCA Copilot.

## Structure

### `kpi/raw/`

Original KPI/statistics datasets provided for research.

Do not modify files in this directory.

This directory is excluded from Git.

### `kpi/processed/`

Normalized KPI datasets generated from the raw source.

### `logs/raw/`

Original operational log datasets.

Excluded from Git.

### `logs/processed/`

Normalized/index-ready operational logs.

### `knowledge/raw/`

Private troubleshooting documents, runbooks, and RCA references.

### `demo/`

Sanitized or synthetic datasets safe for development, automated tests,
documentation, and GitHub.

| File | Purpose |
|---|---|
| `sample_kpi.csv` | Four 60-point anomaly/forecast series with domain correlation |
| `sample_logs.jsonl` | 400 operational events with explicit component and interface fields |
| `sample_incidents.json` | Three supported incidents plus one abstention incident |
| `sample_ground_truth.json` | Expected evidence, topology, knowledge, and RCA status |
| `sample_knowledge.json` | Synthetic runbooks used only for investigation/resolution |
| `sample_scenarios.json` | Stable cross-source scenario manifest |

Regenerate and validate only these synthetic files with:

```powershell
npm run data:generate
npm run data:validate
```

The generator creates missing private directories but never opens or copies files from them.

## Data Safety

Real operator/customer data must never be committed to the repository.

Only anonymized or synthetic data may be stored under `demo/`.
