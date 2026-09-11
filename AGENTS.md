# AGENTS.md

## Purpose

This repository is a proof-of-concept research project for adaptive espresso dial-in. The primary goal is to determine whether manually entered shot data can produce better next-shot recommendations with less wasted coffee than simple dial-in heuristics.

## Before making substantive changes

Read at least:

- `README.md`
- `docs/model.md`
- `docs/research-methods.md`
- `docs/data-model.md`
- `docs/validation.md`
- `docs/decision-log.md`

Treat the decision log as authoritative for current project decisions. Treat modelling ideas explicitly labelled as hypotheses as unproven until validated.

## Engineering and modelling principles

- Keep the proof of concept small.
- Optimize for learning whether the model works, not for product polish.
- Prefer simple models until extra complexity demonstrates out-of-sample/prospective value.
- Prefer gray-box / structured statistical models when useful process structure is already known; do not make a flexible black box relearn obvious physics without a reason.
- Keep optimizer/domain logic independent from Streamlit and SQLite.
- Preserve raw measurements; derive transformed values separately.
- Store recommendations and experiment intent before their outcomes are known.
- Preserve chronology and bean/session boundaries.
- Never silently fill missing/uncertain historical data.
- Distinguish normal assisted shots from deliberately designed Learning/Experiment-mode shots.
- Designed experiments should have an explicit identification question, controlled variables, and replication/stopping logic where practical.
- Do not force purging; retention handling is an experiment, not an assumption.
- Do not require real-time hardware integration for the MVP.
- Robustness to bad/channeling-like shots is a core requirement.
- Actual final yield must be retained and used; do not pretend every shot ended at exactly 36 g.
- Manual correction of puck dose to the target is a supported controlled intervention and must not overwrite grinder output.

## Initial implementation direction

Preferred PoC stack:

- Python 3.12+
- Streamlit
- SQLite
- NumPy / SciPy
- pytest
- Jupyter notebooks for model exploration/backtesting

A future production frontend/backend architecture is explicitly premature until the modelling concept has been validated.

## Repository conventions

- Source code lives under `src/espresso_dialin/`.
- Tests live under `tests/` and should mirror behavior rather than implementation details.
- Exploratory notebooks live under `notebooks/`; reusable logic must move into `src/`.
- Small research datasets with explicit provenance may live under `data/`; runtime databases and generated state must not be committed.
- Dependencies and tool configuration belong in `pyproject.toml`.
- Keep public/core interfaces typed. `mypy` is configured in strict mode for `src/`.
- Use Ruff for both linting and formatting; do not introduce a second formatter/linter without a demonstrated need.
- Do not silently rewrite `data/historical_shots_staging.csv`. Corrections to the transcription should be explicit and reviewable in Git history.
- Do not add a license until the repository owner has explicitly chosen one.

## Quality gates

Before considering a code change complete, run:

```sh
ruff check .
ruff format --check .
mypy src
pytest --cov=espresso_dialin --cov-report=term-missing
```

For normal development, install the pre-commit hooks once:

```sh
pre-commit install
```

CI runs the same core checks on supported Python versions. Do not weaken a quality gate merely to make a change pass; either fix the issue or document why the rule is inappropriate and adjust the configuration deliberately.

## Initial real setup

- Grinder: Baratza Sette 270
- Espresso machine: Sage/Breville Dual Boiler (BES920/SES920)
- Default target: 18.0 g puck dose -> 36.0 g final yield in 30–35 s

Do not hard-code grinder semantics beyond what has been verified. In particular, macro/micro overlap and exact ordering/calibration should be treated as a grinder-adapter concern and tested/verified rather than assumed.

## Validation discipline

When adding or comparing models:

1. establish a simple baseline;
2. use chronological/rolling validation and prospective evaluation where possible;
3. avoid data leakage;
4. report prediction error and, where possible, uncertainty calibration;
5. evaluate coffee/shots-to-target and information gained, not fit quality alone;
6. use ablation tests to establish whether added features actually help;
7. do not claim causal process effects from operator-adapted observational data when a designed experiment is required;
8. record the experiment/recommendation before the result so the evaluation target cannot be chosen retrospectively.

If a complex model does not materially beat a simpler model, keep the simpler model.

## Research-method progression

Candidate methods should be introduced only when the current data can test their assumptions/value:

- proportional / median / human-style baselines;
- structured regression and recursive least squares;
- robust residual models;
- recency/forgetting only if drift is demonstrated;
- state-space/retention terms only if temporal-state signal is demonstrated;
- Gaussian-process surrogates only with a defensible action-space representation and calibratable uncertainty;
- Bayesian optimisation / active experiment selection only after simpler DoE-style Learning Mode is established.

Do not select methods because they are sophisticated. Select them because they answer a concrete identification/control question better than the simpler alternative.

## Scope control

Do not introduce the following without a specific validated need:

- accounts/authentication;
- cloud sync;
- PostgreSQL;
- public API;
- Bluetooth scale support;
- machine telemetry;
- pump-stop detection;
- neural networks;
- elaborate grinder calibration databases;
- taste/preference ML.

These are later extensions, not prerequisites for validating the core idea.
