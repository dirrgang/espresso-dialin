# Notebooks

Use notebooks for exploratory analysis, visualization, and model comparison over historical or synthetic data.

`01_historical_exploration.ipynb` uses the authoritative `data/historical_shots_corrected.csv`. Its analysis and conclusions were refreshed on 2026-09-14; see [historical-analysis.md](../docs/historical-analysis.md). The [original staging analysis](../docs/historical-analysis-staging-2026-09-11.md) is retained separately for provenance.

Run `mise run setup` to install the locked Python 3.14 development and analysis environment, then run notebooks from the repository root or `notebooks/`. A typical execution command is:

```sh
uv run --locked --group analysis jupyter nbconvert --to notebook --execute --inplace notebooks/01_historical_exploration.ipynb
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
