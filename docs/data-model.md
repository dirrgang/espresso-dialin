# Data model

This is the initial persistence/domain model for the local Python proof of concept. The database schema may differ in naming, but the semantic distinctions below should be preserved.

## Principles

1. **Raw observations are authoritative.** Do not overwrite measured values with corrected/derived values.
2. **Recommendations are stored before outcomes are known** so prediction quality can be evaluated honestly.
3. **Experiment intent is stored before outcomes are known.** A deliberately designed Learning-Mode shot must remain distinguishable from normal assisted use.
4. **Historical data may be uncertain.** Missing or approximate values should be represented explicitly rather than guessed.
5. **Chronological order matters**, especially for testing retention / previous-grinder-state effects.
6. Model parameters may be cached later, but should be reconstructable from observations whenever practical.

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

Bean identity matters because a grinder setting is not expected to yield identical extraction behavior across coffees.

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

`shot_mode` should distinguish ordinary use from designed experiments even if no separate `Experiment` entity is implemented in the earliest schema.

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

**TO_TARGET**

The user adjusted the dose to the session target without recording a second precise mass:

```text
grinder_output_g = 17.6
puck_dose_g ~= session.target_puck_dose_g
puck_dose_uncertainty_g = explicit/configured estimate
```

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

`purpose` should distinguish at least whether the recommendation is trying to optimize the immediate drink or execute an information-seeking Learning-Mode experiment, e.g.:

```text
ASSISTED_DIAL_IN
LEARNING_EXPERIMENT
```

For a Learning-Mode recommendation, `metadata_json` may later contain the candidate set, acquisition score, or experimental contrast that motivated the action. These are explanatory records, not post-hoc annotations.

This prevents retrospective leakage when evaluating prediction accuracy or experiment-selection quality.

## Historical handwritten data

An existing handwritten sheet contains approximately the following columns:

```text
grinder setting
grind duration
recorded grinder output
brew duration
final beverage yield
```

At least one bean change is visibly marked (“neue Bio Espresso”), and other session/bean boundaries may need manual confirmation.

Important import semantics:

- the recorded coffee mass is **grinder output**, not necessarily puck dose;
- the user generally corrected non-18-g output to approximately 18 g before brewing;
- therefore set `dose_correction_mode = TO_TARGET` when this behavior is known;
- do not pretend the handwritten output mass was the brewed dose;
- preserve row order exactly;
- preserve uncertain handwriting as `null`/uncertain with a transcription note;
- never infer a missing value merely to make a row complete;
- preserve known bean/session boundaries;
- historical rows have no reliable predeclared Learning-Mode intent and must not be retrospectively labelled as designed experiments.

A CSV staging format is useful before database import, for example:

```text
sequence,bean_label,grind_macro,grind_micro,grind_duration_s,grinder_output_g,dose_correction_mode,puck_dose_g,brew_duration_s,final_yield_g,transcription_status,notes
```

## Derived values

Derived values should generally not replace raw measurements. Examples:

```text
t36_linear_approx_s
prediction_residual
outlier_weight
effective_grind_state
```

They can be calculated at analysis time or cached with a model/version identifier.

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
