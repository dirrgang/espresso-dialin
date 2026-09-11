# Next steps

The project should validate the modelling assumptions before spending time on product architecture.

## Phase 0 — Historical dataset

1. Transcribe the existing handwritten shot sheet into a staging CSV.
2. Preserve exact row order.
3. Mark bean/session boundaries that are known.
4. Mark uncertain/illegible cells explicitly rather than guessing.
5. Record historical dose correction as `TO_TARGET` where the puck was manually corrected to approximately 18 g.
6. Keep the original grinder-output mass separately from the approximate brewed dose.

Deliverable: a versioned raw/staging dataset plus a short transcription note describing uncertainty.

## Phase 1 — Exploratory notebook

Before building a UI, inspect the historical data:

- grind duration vs. grinder output;
- grinder setting vs. brew duration/final yield;
- variation at repeated settings;
- effect of actual final-yield deviation;
- residual/outlier distribution;
- first shot after a setting change vs. repeated shots at the same setting;
- differences across known bean/session boundaries.

Deliverable: notebook with plots/statistics and explicit conclusions about which modelling assumptions are worth pursuing.

Completed 2026-09-11: [`01_historical_exploration.ipynb`](../notebooks/01_historical_exploration.ipynb)
and [`historical-analysis.md`](historical-analysis.md). The 51-row audit uses separate
eligibility rules, retains raw yield/output and compares simple chronological baselines.
Linear normalization does not consistently improve repeatability; retention evidence is
insufficient. These are limited empirical findings, not validated physical laws.

## Phase 2 — Baseline models

Immediate next step after the historical analysis: a small typed proportional-dose
baseline, compared with a past-only same-block median output rate, with explicit
recommendation records for prospective evaluation. Only 17 compatible historical
dose pairs exist. Defer extraction regression until targeted repeats better resolve
setting/session/yield confounding; do not automatically adopt linear T36 as ground truth.
The following remains the broader baseline agenda, not authorization to skip that validation.

Implement and test:

1. human-style direction heuristic;
2. proportional grind-duration correction;
3. simple static regression for extraction;
4. raw-time vs. linear yield-normalized baseline.

Use rolling chronological validation.

Deliverable: baseline metrics that later models must beat.

## Phase 3 — Robust / richer models

Add incrementally:

1. robust residual handling;
2. learned use of `(brew_duration, final_yield)`;
3. grinder-output model including current grind setting;
4. simple previous-setting/change features;
5. retention latent state only if simpler previous-setting features improve validation.

Use ablation tests for every major addition.

## Phase 4 — Minimal local application

Only after the core recommendation loop is plausible, build the Streamlit + SQLite workflow:

```text
Select/start session
    -> show next recommendation
    -> enter grinder output
    -> mark corrected-to-target or actual puck dose
    -> enter brew duration and final yield
    -> save shot
    -> generate/store next recommendation
```

The UI must not contain model logic.

## Phase 5 — Prospective test

Use new beans to test actual convergence:

- store every recommendation before the shot;
- follow it as closely as practical;
- record actual settings/measurements;
- track shots-to-target and grams-to-target;
- compare with baseline recommendation strategies where practical.

## Phase 6 — Decide whether to continue

Continue toward a real web/mobile product only if the PoC shows practical value.

Possible later extensions, in approximate order of likely usefulness:

- better grinder profiles/adapters;
- import/export;
- cross-session priors / bean ageing or calibration epochs;
- optional taste/preference feedback;
- proper PWA/web frontend + Python API;
- synchronization/accounts;
- Bluetooth-scale or machine integrations;
- pump-stop/afterflow modelling.

Hardware telemetry should remain a stretch goal rather than contaminating the initial proof-of-concept scope.
