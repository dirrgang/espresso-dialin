# Next steps

The project should validate modelling assumptions with prospective data and deliberately designed experiments before spending heavily on product architecture or advanced models.

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

## Phase 2 — Baseline dose models

Completed 2026-09-11: the small typed proportional-dose baseline and past-only
same-block/exact-setting median-rate comparator, with explicit prospective recommendation
records and scoring. See [`dose-control-baseline.md`](dose-control-baseline.md). The rolling
rate evaluation has 22 predictions per strategy (21 in the earlier incompletely identified
block and one in the newer block). Median-rate is numerically better but does not establish
material superiority.

The baselines define the minimum standard that richer grinder-output models must beat.

## Phase 3 — Minimal prospective data-acquisition application

Build the smallest useful Streamlit + SQLite vertical slice early enough that future shots are prospective, timestamped, and linked to recommendations created before outcomes are known.

Required flow:

```text
Select/start session
    -> choose current/manual grind setting
    -> create and persist next dose recommendation (or manual fallback)
    -> grind and record actual duration + grinder output
    -> record dose correction / puck dose
    -> brew and record duration + final yield
    -> save outcome linked to the frozen recommendation
```

Persist at minimum:

- sessions / bean identity and targets;
- timezone-aware timestamps;
- recommendations and model/version/source observations;
- recommended versus actual grinder setting/duration separately;
- raw grinder output;
- dose-correction mode and actual/approximate puck dose;
- brew duration and final yield;
- optional bad-shot / purge / notes metadata.

The UI must not contain model logic. Data collection must never be blocked because a model has insufficient history.

Deliverable: an application that can already be used during normal espresso preparation even while grind-setting optimisation remains manual.

## Phase 4 — Learning / Experiment mode and first designed experiments

Add an explicit experiment intent distinct from normal assisted use. The first version should use transparent Design-of-Experiments principles rather than autonomous Bayesian optimisation.

Initial experiment families should be selected for concrete identification questions, for example:

1. **Repeatability / noise**
   - repeat identical setting + duration several times;
   - estimate within-condition grinder-output and extraction variability.

2. **Grind-duration response**
   - hold exact setting and bean/session fixed;
   - deliberately vary duration around the normal operating point;
   - test proportionality and whether an intercept/nonlinearity is measurable.

3. **Setting effect on grinder output**
   - repeat nearby settings at controlled durations;
   - determine whether output rate materially depends on setting.

4. **Extraction response to setting**
   - keep puck dose approximately fixed via manual correction;
   - test selected neighbouring settings with replication;
   - use `(brew_duration, final_yield)` jointly rather than treating linear `T36` as truth.

5. **Transition / retention signal**
   - deliberately compare first shot after a setting change with an immediate repeat;
   - repeat enough transitions to determine whether a previous-setting/state term has prospective value.

6. **Drift**
   - revisit a reference condition later in the same bean/session;
   - test whether time/ageing/state changes are large enough to justify recency weighting or a forgetting factor.

Predefine the question, experimental points, replication, and stopping criterion before examining results where practical.

Deliverable: a small prospective dataset with known experimental intent that can separate process effects from ordinary shot noise better than the historical notes can.

See [`research-methods.md`](research-methods.md).

## Phase 5 — Structured system identification / richer models

Add complexity incrementally based on the prospective evidence.

Candidate progression:

1. structured regression for grinder output, including setting effects if demonstrated;
2. recursive least squares / adaptive estimation if online updating is useful;
3. forgetting/recency weighting only if measurable drift exists;
4. robust residual handling where anomalous observations materially affect prediction;
5. learned joint use of `(brew_duration, final_yield)` for extraction;
6. simple previous-setting/change features;
7. latent state-space retention model only if the simple temporal features add validated value;
8. Gaussian-process surrogate only when the grinder/action representation and data density make its uncertainty useful.

Use ablation tests for every major addition and compare every richer model with the existing baselines.

## Phase 6 — Active experiment selection / Bayesian optimisation

Only after the surrogate model and uncertainty estimates are credible, evaluate whether Learning Mode should choose experiments using an acquisition function rather than a fixed DoE schedule.

Possible objectives include:

- expected improvement in dial-in quality;
- expected information gain / entropy reduction;
- knowledge gradient;
- explicitly constrained trade-offs between information gained and coffee consumed.

Do not treat Bayesian optimisation as a prerequisite. It must beat transparent experiment schedules or provide useful capabilities they cannot.

## Phase 7 — Prospective closed-loop evaluation

Use new beans/sessions to test actual convergence:

- store every recommendation before the shot;
- follow it as closely as practical;
- record actual settings/measurements and deviations;
- track shots-to-target and grams-to-target;
- compare baseline and richer strategies using a schedule fixed before outcomes;
- evaluate prediction error, calibration, convergence, oscillation, and waste.

Designed Learning-Mode shots and normal-use shots must remain distinguishable in analysis.

## Phase 8 — Decide whether to continue toward a product

Continue toward a real web/mobile product only if the modelling/control approach shows practical value.

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
