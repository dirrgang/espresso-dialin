# Data model

This is the initial persistence/domain model for the local Python proof of concept. The database schema may differ in naming, but the semantic distinctions below should be preserved.

Project-wide mathematical symbols are defined in [`notation.md`](notation.md). Where database fields correspond directly to those symbols, the mapping is stated explicitly below.

## Principles

1. **Raw observations are authoritative.** Do not overwrite measured values with corrected/derived values.
2. **Recommendations are stored before outcomes are known** so prediction quality can be evaluated honestly.
3. **Experiment intent is stored before outcomes are known.** A deliberately designed Learning-Mode shot must remain distinguishable from normal assisted use.
4. **Historical data may be uncertain.** Missing or approximate values should be represented explicitly rather than guessed.
5. **Chronological order matters**, especially for testing retention / previous-grinder-state effects.
6. Model parameters may be cached later, but should be reconstructable from observations whenever practical.

## Mathematical field mapping

For shot $n$, the central persisted measurements map to the notation in [`notation.md`](notation.md) as follows:

| Persistence field | Mathematical symbol | Meaning |
| --- | --- | --- |
| `grind_setting` | $G_n$ | Grinder setting actually used |
| `grind_duration_s` | $t_{\mathrm{grind},n}$ | Actual grinder run time |
| `grinder_output_g` | $D_{\mathrm{out},n}$ | Raw grinder output before manual correction |
| `puck_dose_g` | $D_{\mathrm{puck},n}$ | Coffee mass actually brewed after correction |
| `brew_duration_s` | $t_{\mathrm{brew},n}$ | Recorded brew duration |
| `final_yield_g` | $Y_n$ | Final beverage yield |

Session target fields map similarly:

- `target_puck_dose_g` -> $D_{\mathrm{puck}}^{\ast}$;
- `target_yield_g` -> $Y^{\ast}$;
- `target_time_min_s` / `target_time_max_s` -> the acceptable brew-duration interval.

A future raw-grinder-output target can be represented mathematically as $D_{\mathrm{out}}^{\ast}$ even if it is initially numerically equal to the puck-dose target. Keeping those concepts distinct matters because the puck may be corrected after grinding.

## Entities

### Grinder

Suggested fields:

```text
id
name
manufacturer?
model?
adjustment_type
adjustment_definition
finer_direction
notes?
```

`adjustment_type` candidates:

```text
STEPPED_NUMERIC
MACRO_MICRO
STEPLESS_NUMERIC
RELATIVE
```

`adjustment_definition` should describe the actions/settings the user can physically select. It must not imply a calibrated physical particle-size scale unless such calibration exists.

Initial real grinder: Baratza Sette 270. Exact macro/micro ordering and overlap behavior are to be verified before encoding strong assumptions.

### Bean

Suggested fields:

```text
id
name
roaster?
roast_date?
opened_at?
notes?
```

Bean identity matters because a grinder setting is not expected to yield identical extraction behavior across coffees. In mathematical discussion, bean/session context may be abbreviated as $B_n$; that symbol is contextual shorthand rather than a scalar physical measurement.

### DialInSession

A session groups a chronological sequence for one coffee/target/setup.

```text
id
bean_id
grinder_id
started_at
ended_at?
target_puck_dose_g
target_yield_g
target_time_min_s
target_time_max_s
notes?
```

Default targets:

```text
target_puck_dose_g = 18.0
target_yield_g = 36.0
target_time_min_s = 30.0
target_time_max_s = 35.0
```

Do not assume every future session uses these defaults.

### Experiment / Learning plan

A planned experiment records **why** one or more shots are being requested before their results are known.

Conceptual fields:

```text
id
session_id
created_at
mode
question
plan_type
planned_conditions_json
replication_target?
stopping_rule_json?
coffee_budget_g?
status
notes?
```

`mode` should distinguish at least:

```text
NORMAL
LEARNING
```

Possible `plan_type` values may eventually include:

```text
REPEATABILITY
DURATION_RESPONSE
SETTING_COMPARISON
TRANSITION_RETENTION
DRIFT_REFERENCE
CUSTOM
```

Do not hard-code a large taxonomy prematurely; the essential semantic requirement is that designed experiments are identifiable and that their intended question/conditions were recorded before outcomes.

A later Bayesian/active-learning system may generate an experiment plan automatically. The persistence semantics should remain the same: the selected experimental action and its rationale/acquisition metadata are frozen before the shot.

### Shot

Core raw observation:

```text
id
session_id
sequence
timestamp?
experiment_id?
shot_mode

grind_setting
grind_duration_s
grinder_output_g

dose_correction_mode
puck_dose_g?
puck_dose_uncertainty_g?

brew_duration_s
final_yield_g

purged_before_shot?
user_quality_flag?
notes?
source
```

`sequence` provides the chronological shot index $n$ within the relevant session/order semantics. `shot_mode` should distinguish ordinary use from designed experiments even if no separate `Experiment` entity is implemented in the earliest schema.

#### Dose correction

Avoid a bare boolean in the long-term schema. Use at least:

```text
NONE
TO_TARGET
MEASURED
```

Semantics:

**NONE**

```text
grinder_output_g = 17.6
puck_dose_g = 17.6
```

In notation, this means $D_{\mathrm{puck},n}=D_{\mathrm{out},n}$ for that shot.

**TO_TARGET**

The user adjusted the dose to the session target without recording a second precise mass:

```text
grinder_output_g = 17.6
puck_dose_g ~= session.target_puck_dose_g
puck_dose_uncertainty_g = explicit/configured estimate
```

Mathematically, $D_{\mathrm{out},n}$ remains the measured raw output while $D_{\mathrm{puck},n}$ is approximately $D_{\mathrm{puck}}^{\ast}$ with explicitly represented uncertainty.

**MEASURED**

The corrected puck dose was weighed again:

```text
grinder_output_g = 17.6
puck_dose_g = 18.07
```

The UI can still expose the common case as a simple checkbox (“Corrected to 18.0 g”) while storing richer semantics underneath.

#### User quality flag

Optional values could include:

```text
NORMAL
OBVIOUSLY_BAD
```

Do not require the user to diagnose channeling. Robust statistics should be the primary defense against anomalous shots.

#### Source

Suggested values:

```text
LIVE
HISTORICAL_TRANSCRIPTION
IMPORT
```

### Recommendation

Store every actionable prediction before the associated shot is brewed.

```text
id
session_id
experiment_id?
created_at
based_on_through_shot_sequence
model_id
model_version
purpose

recommended_grind_setting
recommended_grind_duration_s

expected_grinder_output_g?
expected_grinder_output_uncertainty_g?
expected_t36_s?
expected_t36_uncertainty_s?

metadata_json?
```

Where useful in mathematical analysis:

- `recommended_grind_duration_s` corresponds to $t_{\mathrm{grind},n}^{\mathrm{rec}}$;
- the actual `Shot.grind_duration_s` corresponds to $t_{\mathrm{grind},n}^{\mathrm{actual}}$;
- `expected_grinder_output_g` corresponds to a prediction such as $\hat D_{\mathrm{out},n}$;
- `expected_t36_s` corresponds to a model estimate $\hat T_{36}$, **not** to the historical linear approximation unless that model explicitly says so.

`purpose` should distinguish at least whether the recommendation is trying to optimize the immediate drink or execute an information-seeking Learning-Mode experiment, e.g.:

```text
ASSISTED_DIAL_IN
LEARNING_EXPERIMENT
```

For a Learning-Mode recommendation, `metadata_json` may later contain the candidate set, acquisition score, or experimental contrast that motivated the action. These are explanatory records, not post-hoc annotations.

This prevents retrospective leakage when evaluating prediction accuracy or experiment-selection quality.

## Derived values

Derived values should generally not replace raw measurements. Examples:

```text
t36_linear_approx_s
prediction_residual
outlier_weight
effective_grind_state
```

`t36_linear_approx_s` corresponds specifically to the crude derived quantity $T_{36}^{\mathrm{linear}}$ defined in [`notation.md`](notation.md). It is not a measured target-time value.

`prediction_residual`, `outlier_weight`, and `effective_grind_state` are intentionally generic names: their precise mathematical definitions depend on the model/version that produced them and must be stored or documented with that model. They should not acquire an implicit cross-model meaning merely because the field names look familiar.

Derived values can be calculated at analysis time or cached with a model/version identifier.

## SQLite notes

For the PoC, SQLite is sufficient. Prefer a thin repository layer so Streamlit and optimizer code do not issue ad-hoc SQL directly.

Likely tables:

```text
grinders
beans
dial_in_sessions
experiments
shots
recommendations
```

The initial live app may omit a separate `experiments` table if Learning Mode is not yet implemented, provided shot/recommendation schemas can later add experiment identity without losing semantic distinctions.

Schema migrations can remain simple initially, but a schema version should exist before importing a meaningful historical or prospective dataset.

## Original live schema (version 1)

Phase 3 originally used three tables with `PRAGMA user_version = 1`. Phase 3.1 adds the
v2 changes below; current schema definitions and migration live in `src/espresso_dialin/schema.py`.

| Table | Persisted fields |
| --- | --- |
| `sessions` | ID, bean ID/name, optional roaster/roast date, UTC started/ended timestamps, grinder/machine identities, puck/yield/time targets |
| `recommendations` | ID, session ID, target sequence, UTC creation timestamp, applicable setting, planned duration, target output, strategy/model version, nullable rate/expected output, model JSON, selected flag |
| `shots` | ID, session ID, sequence, UTC creation/completion timestamps, selected recommendation ID, actual setting/duration/output, correction mode, nullable measured puck dose, brew duration/yield, purge/bad flags, notes |

All records in this schema are prospective normal-use records; no historical import or
Learning/Experiment-mode records are created. Recommendation `model_json` is the unchanged
controller serialization, including exact source observation IDs, block identity, observation
count and history-through sequence. It is null for a `manual` plan, as are the rate and expected
output fields. A manual plan records intent without masquerading as a statistical prediction.

The selected flag is immutable pre-shot intent, with exactly one selected plan linked to each
shot. Execution is represented separately by actual measurements. Multiple unselected model
predictions are preserved for prospective comparison. Session/sequence foreign keys and unique
indexes enforce linkage and one pending shot per session. Frozen recommendation and completed
source observation updates/deletes are rejected; see [live-workflow.md](live-workflow.md).

For live `NONE` and `TO_TARGET`, `puck_dose_g` is null: this column records only a separately
measured puck mass. `NONE` declares brewed mass equal to output; `TO_TARGET` declares approximate
control at the session target with unquantified uncertainty. Neither declaration creates a
second precise measurement. `MEASURED` requires a positive finite puck mass. Incomplete shots
have null grinding/brewing fields until each corresponding phase is saved.

## Current live schema (version 2)

- `sessions.bag_opened_date`: optional ISO calendar date for the physical package. Bean
  product identity remains separate; no lot identifier or automatic pooling is introduced.
- `shots.grinding_recorded_at`: optional UTC acquisition timestamp. New successful grinding
  saves populate it atomically with the measurements; migrated measurements retain null.
- `shot_resolutions`: `shot_id` (primary/foreign key), `status` (`ABANDONED` or `INVALIDATED`),
  UTC `recorded_at`, and required `reason`. Each row is immutable and does not UPDATE its shot.

`Shot.status` derives `PENDING_GRINDING`, `PENDING_BREWING`, or `COMPLETED` from existing phase
evidence, overridden by a resolution when present. This avoids duplicating state that could
disagree with the saved measurements. `plan_frozen_at` aliases `created_at` and
`brewing_recorded_at` aliases `completed_at`; no physical-event timing is inferred.

Pending shots may be abandoned or invalidated. Completed shots may only be invalidated.
A shot gets at most one resolution; subsequent resolutions and all later phase writes are
rejected. Saved grinder data, completed outcomes, and frozen predictions remain unchanged.
An abandoned brew retains its grinder observation as valid; invalidation excludes the entire
shot. Missing/invalid grinder observations break the conservative contiguous setting block.

The v1-to-v2 migration uses explicit ALTER/DDL steps under a single transaction. It preserves
every existing value and does not manufacture timestamps or lifecycle annotations. It replaces
the old pending-shot index with a trigger that accounts for resolutions, and adds guards for
saved grinder measurements, phase timing and bag context. Fresh databases use v2 definitions
directly. The original v1 SQL fixture in `tests/fixtures/schema_v1.sql` verifies real migration,
data preservation, idempotence and rollback after failure.
