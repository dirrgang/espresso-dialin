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
\frac{D_{\mathrm{out}}^*}{D_{\mathrm{out,old}}}.
```

`old` and `new` denote successive controller actions, not necessarily adjacent absolute shot numbers in every analysis.

### C. EspressoPost-like static model

A simple regression from current grinder setting (optionally basic covariates) to brew-time behavior, without retention state and without the richer grinder-output/yield treatment.

This is a conceptual baseline; do not claim exact equivalence to EspressoPost unless reproducing its published algorithm faithfully.

## Candidate models

Increment complexity only when justified:

1. simple regression;
2. + actual yield handling;
3. + dose/output model;
4. + robust residual handling;
5. + previous-setting / retention feature;
6. + latent retention state;
7. Bayesian uncertainty model if useful.

Ablation tests are important: compare a rich model with the same model minus one feature to measure the feature's actual contribution.

## Historical rolling validation

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

Where recommended and actual actions differ, keep them separate using notation such as $t_{\mathrm{grind},n}^{\mathrm{rec}}$ and $t_{\mathrm{grind},n}^{\mathrm{actual}}$ rather than silently substituting one for the other.

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

The handwritten dataset is observational and was generated by a human adapting settings deliberately. It therefore has selection bias and correlated inputs. Treat conclusions cautiously.

In particular:

- settings were not randomized;
- bean identity/session boundaries may be incomplete;
- puck dose was usually corrected to approximately 18 g;
- some handwritten values may be uncertain;
- unrecorded puck-preparation quality can create large residuals.

Historical data are useful for warm-starting and rejecting obviously bad model ideas, but prospective trials are the real test.
