# Notebooks

Use notebooks for exploratory analysis, visualization, and model comparison over historical or synthetic data.

`01_historical_exploration.ipynb` is the original historical-analysis notebook. Its committed outputs and current data-path reference still represent the **staging transcription snapshot** used for the 2026-09-11 analysis. Those numeric results remain useful as an audit trail, but they are no longer the current historical source of truth.

For new/repeated historical analyses, use `data/historical_shots_corrected.csv`, which incorporates user-supplied corrections and the now-known bean identities. The notebook should be updated/rerun against that corrected dataset before new numeric conclusions are treated as current. The corresponding historical note in [`historical-analysis.md`](../docs/historical-analysis.md) should likewise be treated as a snapshot until regenerated.

Install `.[dev,analysis]`, then run notebooks from the repository root or `notebooks/`. A typical execution command is:

```sh
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_historical_exploration.ipynb
```

Clear generated outputs before committing; retain empirical conclusions in the research note.

Guidelines:

- keep reusable model/domain logic in `src/espresso_dialin/`, not in notebook-only cells;
- make data sources and transformations explicit;
- preserve chronological train/test boundaries for backtests;
- avoid committing large generated outputs or embedded binary data;
- treat notebooks as experiments, not as the authoritative implementation;
- use `data/historical_shots_corrected.csv` for current historical modelling unless explicitly studying transcription uncertainty;
- when an experiment materially changes a project decision, update the relevant document under `docs/` and the decision log.
