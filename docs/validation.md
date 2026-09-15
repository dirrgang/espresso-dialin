# Validation and experiment plan

The proof of concept succeeds only if it improves real dial-in decisions out of sample. This document defines how to test that claim without fooling ourselves.

Project-wide espresso symbols are defined in [`notation.md`](notation.md). Validation-specific notation is introduced below where needed.

## Research question

Primary question:

> Can a learning model using manually available espresso measurements reach a target recipe with fewer shots / less wasted coffee than simple human-style dial-in heuristics?

Secondary questions:

1. Does using actual final yield improve target-time prediction compared with treating every shot as if it ended at 36 g?
2. Does grinder-output history materially improve grind-duration recommendations?
3. Does robust regression reduce harmful overreaction to anomalous shots?
4. Does previous grinder setting contain enough signal to justify a retention/dead-space state model?
5. Are grinder-specific nonlinear/overlapping adjustment mappings useful enough to justify extra complexity?

## Baselines

At minimum compare against:

### A. Human-style heuristic

- shot too fast -> grind finer;
- shot too slow -> grind coarser;
- grinder output too low -> increase grind duration;
- grinder output too high -> decrease grind duration.

### B. Simple proportional dose controller

Using the notation from [`notation.md`](notation.md), the generic proportional update is:

```math
t_{\mathrm{grind,new}}
=
t_{\mathrm{grind,old}}
\frac{D_{\mathrm{out}}^{\ast}}{D_{\mathrm{out,old}}}.
```

`old` and `new` denote successive controller actions, not necessarily adjacent absolute shot numbers in every analysis.

### C. EspressoPost-like static model

A simple regression from current grinder setting (optionally basic covariates) to brew-time behavior, without retention state and without the richer grinder-output/yield treatment.

This is a conceptual baseline; do not claim exact equivalence to EspressoPost unless reproducing its published algorithm faithfully.

## Candidate models

Increment complexity only when justified:

1. simple regression;
2. - actual yield handling;
3. - dose/output model;
4. - robust residual handling;
5. - previous-setting / retention feature;
6. - latent retention state;
7. Bayesian uncertainty model if useful.

Ablation tests are important: compare a rich model with the same model minus one feature to measure the feature's actual contribution.

## Historical rolling validation

Use `data/historical_shots_corrected.csv` as the authoritative current historical dataset. The staging CSV and staging-based notebook/results remain provenance artifacts rather than current benchmark inputs.

Let $S_n$ denote the $n$th chronological shot within the relevant bean/session sequence. Never train on the observation being predicted.

Example:

```text
train S1..S5 -> predict S6
train S1..S6 -> predict S7
train S1..S7 -> predict S8
...
```

Do this within appropriate bean/session boundaries and with any global cross-session priors handled explicitly.

This can test prediction quality, but it cannot prove what would have happened under an unobserved alternative recommendation. Prospective testing is required for that.

## Prospective validation

Once a model is usable:

1. Start a new bean/session.
2. Record the recommendation before brewing.
3. Brew according to the recommendation as closely as practical.
4. Record actual grinder output, correction status, brew duration, and final yield.
5. Store the observation.
6. Generate the next recommendation.

Do not overwrite historical recommendations after model updates.

Phase 3 now persists both available dose-model predictions before grinding, even when the
selected action is manual. Use each frozen rate at the actual recorded grind duration for
later prediction evaluation, and require an exact match between actual and applicable setting.
Do not assign the observed output to an unexecuted shadow duration. The application does not
yet report comparative efficacy or coffee savings. Its automated tests establish acquisition
integrity and restart behavior, not model superiority; see [live-workflow.md](live-workflow.md).

Where recommended and actual actions differ, keep them separate using notation such as $t_{\mathrm{grind},n}^{\mathrm{rec}}$ and $t_{\mathrm{grind},n}^{\mathrm{actual}}$ rather than silently substituting one for the other.

## Phase 3.1 integrity and eligibility

Acquisition tests include migration of a populated original v1 database, rollback after a
forced migration failure, phase timestamp ordering, immutable abandonment/invalidation,
restart recovery, and confirmation/reason requirements in the Streamlit UI. These checks
establish data integrity, not model efficacy.

Future dose history excludes invalidated shots. A brew explicitly abandoned with valid grinder
data can still contribute under the normal exact-actual-setting rule. A pre-grind abandonment
requires explicit confirmation that no physical grinding occurred; it contributes no observation
but is transparent to grinder continuity. Invalidation remains a conservative block boundary
even when grinder fields are missing. No other missing data may be interpreted as non-execution
or bridged. Invalidation does not refit already-frozen predictions; analyses should distinguish
what was known at freeze time from errors discovered later, and should not score invalid outcomes
as trustworthy measurements. The resolution timestamp and retained original rows support that
distinction. Acquisition timestamps must not be used as exact physical grinder/pump-event timings.

## Metrics

### Prediction metrics

Possible metrics:

- MAE / RMSE of grinder output prediction;
- MAE / RMSE of estimated $T_{36}$ or another explicitly defined target-time representation;
- sign accuracy (did the model correctly predict that a change would be faster/slower?);
- interval coverage / calibration if uncertainty intervals are emitted.

Analyses that report signed residuals must define their sign convention. [`dose-control-baseline.md`](dose-control-baseline.md), for example, uses prediction minus observation.

### Dial-in outcome metrics

Define an explicit target region rather than exact equality. Initial candidate:

```text
puck dose: approximately 18 g
final yield: approximately 36 g
brew time: 30–35 s
```

The exact tolerated dose/yield bands should be decided before comparative trials, not adjusted after seeing results.

Then measure:

- number of brewed shots until target region is reached;
- total coffee ground until target region is reached;
- coffee discarded for purging, if any;
- number/magnitude of manual dose corrections;
- number of reversals/oscillations in grinder recommendations.

A useful aggregate objective is:

```text
dial_in_cost = total grams of coffee consumed before first acceptable recipe
```

This matches the low-waste motivation better than prediction error alone.

## Robustness tests

Synthetic tests should deliberately inject:

- one extremely fast shot (channeling-like outlier);
- one extremely slow shot;
- noisy grinder output;
- missed target yield (+/- several grams);
- a large grinder-setting change followed by repeated shots at the new setting;
- missing optional values;
- approximate dose correction rather than exact puck dose.

The desired behavior is stable recommendations and appropriately increased uncertainty, not aggressive reaction to one implausible point.

## Retention test

Before implementing a complicated latent-state model, test simpler evidence for retention.

For example, evaluate whether prediction improves when adding explicit features such as:

```text
previous_grind_setting
setting_changed
first_shot_after_setting_change
```

Do **not** define `change_from_previous_setting` as arithmetic subtraction unless a validated numeric grinder representation $z(G)$ exists. For opaque Sette-style settings, transition features should remain categorical/structured as described in [`notation.md`](notation.md).

If these features do not improve chronological out-of-sample metrics, do not add a retention model merely because it is physically plausible.

## Yield handling test

Compare at least:

1. ignore yield and use raw brew duration $t_{\mathrm{brew}}$;
2. use the crude linear normalization:

```math
T_{36}^{\mathrm{linear}}
=
t_{\mathrm{brew}}\frac{36}{Y};
```

3. learn a relationship using both $t_{\mathrm{brew}}$ and final yield $Y$.

$T_{36}^{\mathrm{linear}}$ is defined in [`notation.md`](notation.md) as a derived approximation, not ground truth.

This directly tests one of the project's main hypotheses.

## Historical-data limitations

The historical dataset is observational and was generated by a human adapting settings deliberately. It therefore has selection bias and correlated inputs. Treat conclusions cautiously even after the transcription has been corrected.

Known bean identity is no longer the main uncertainty: sequences 1–39 are Café Intención Espresso Intensivo and sequences 40–51 are REWE Bio Espresso ganze Bohnen, 1000 g. Remaining limitations include:

- settings were not randomized;
- exact session/day boundaries within a bean block are not recorded;
- elapsed time, bean age, hopper state and purge/retention state are not fully recorded;
- puck dose was usually corrected to approximately 18 g;
- a small number of measurements remain missing or approximate;
- unrecorded puck-preparation quality can create large residuals.

Historical data are useful for warm-starting, estimating some repeatability, rejecting obviously bad model ideas and deciding which experiments would add information. Prospective trials remain the real test of controller performance.
