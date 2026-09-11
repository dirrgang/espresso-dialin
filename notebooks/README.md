# Notebooks

Use notebooks for exploratory analysis, visualization, and model comparison over historical or synthetic data.

`01_historical_exploration.ipynb` audits the current staging CSV and compares output,
extraction, robust descriptions and chronological baselines by bean block. Install
`.[dev,analysis]`, then run all cells from the repository root or `notebooks/`.
The research record and exact input hash are in [`historical-analysis.md`](../docs/historical-analysis.md).
Execute with `python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_historical_exploration.ipynb`.
Clear generated outputs before committing; retain empirical conclusions in the research note.

Guidelines:

- keep reusable model/domain logic in `src/espresso_dialin/`, not in notebook-only cells;
- make data sources and transformations explicit;
- preserve chronological train/test boundaries for backtests;
- avoid committing large generated outputs or embedded binary data;
- treat notebooks as experiments, not as the authoritative implementation;
- when an experiment materially changes a project decision, update the relevant document under `docs/` and the decision log.
