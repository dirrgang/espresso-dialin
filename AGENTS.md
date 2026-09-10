# AGENTS.md

## Purpose

This repository is a proof-of-concept research project for adaptive espresso dial-in. The primary goal is to determine whether manually entered shot data can produce better next-shot recommendations with less wasted coffee than simple dial-in heuristics.

## Before making substantive changes

Read at least:

- `README.md`
- `docs/model.md`
- `docs/data-model.md`
- `docs/validation.md`
- `docs/decision-log.md`

Treat the decision log as authoritative for current project decisions. Treat modelling ideas explicitly labelled as hypotheses as unproven until validated.

## Engineering principles

- Keep the proof of concept small.
- Optimize for learning whether the model works, not for product polish.
- Prefer simple models until extra complexity demonstrates out-of-sample value.
- Keep optimizer/domain logic independent from Streamlit and SQLite.
- Preserve raw measurements; derive transformed values separately.
- Store recommendations before their outcomes are known.
- Preserve chronology and bean/session boundaries.
- Never silently fill missing/uncertain historical data.
- Do not force purging; retention handling is an experiment, not an assumption.
- Do not require real-time hardware integration for the MVP.
- Robustness to bad/channeling-like shots is a core requirement.
- Actual final yield must be retained and used; do not pretend every shot ended at exactly 36 g.
- Manual correction of puck dose to the target is a supported controlled intervention and must not overwrite grinder output.

## Initial implementation direction

Preferred PoC stack:

- Python
- Streamlit
- SQLite
- NumPy / SciPy
- pytest
- Jupyter notebooks for model exploration/backtesting

A future production frontend/backend architecture is explicitly premature until the modelling concept has been validated.

## Initial real setup

- Grinder: Baratza Sette 270
- Espresso machine: Sage/Breville Dual Boiler (BES920/SES920)
- Default target: 18.0 g puck dose -> 36.0 g final yield in 30–35 s

Do not hard-code grinder semantics beyond what has been verified. In particular, macro/micro overlap and exact ordering/calibration should be treated as a grinder-adapter concern and tested/verified rather than assumed.

## Validation discipline

When adding or comparing models:

1. establish a simple baseline;
2. use chronological/rolling validation;
3. avoid data leakage;
4. report prediction error and, where possible, uncertainty calibration;
5. evaluate coffee/shots-to-target, not fit quality alone;
6. use ablation tests to establish whether added features actually help.

If a complex model does not materially beat a simpler model, keep the simpler model.

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
