# Notebooks

Use notebooks for exploratory analysis, visualization, and model comparison over historical or synthetic data.

Guidelines:

- keep reusable model/domain logic in `src/espresso_dialin/`, not in notebook-only cells;
- make data sources and transformations explicit;
- preserve chronological train/test boundaries for backtests;
- avoid committing large generated outputs or embedded binary data;
- treat notebooks as experiments, not as the authoritative implementation;
- when an experiment materially changes a project decision, update the relevant document under `docs/` and the decision log.
