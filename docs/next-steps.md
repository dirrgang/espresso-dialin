# Next steps

The project should validate modelling assumptions with prospective data and deliberately designed experiments before spending heavily on product architecture or advanced models.

Project-wide mathematical symbols used below are defined in [`notation.md`](notation.md).

## Phase 0 — Historical dataset

Completed.

The repository now keeps two distinct historical artifacts:

- `data/historical_shots_staging.csv` — immutable/auditable initial transcription;
- `data/historical_shots_corrected.csv` — authoritative dataset for current analysis, including later user-supplied corrections/recovered entries.

Known bean identities are now:

- sequences 1–39: Café Intención Espresso Intensivo;
- sequences 40–51: REWE Bio Espresso ganze Bohnen, 1000 g.

The REWE Bio Espresso is also the current bean for the beginning of prospective/live data collection.

## Phase 1 — Historical exploration and gap analysis

Refreshed 2026-09-14 against the corrected source in [`01_historical_exploration.ipynb`](../notebooks/01_historical_exploration.ipynb) and [`historical-analysis.md`](historical-analysis.md), including descriptive/rolling results and focused experiment gaps. The original staging report is archived separately.

Historical repeats already inform variability, but duration/setting effects remain confounded; REWE lacks identical-setting/duration output repeats, and the seven immediate transition/repeat pairs do not identify retention. Use the report’s gap table before selecting Learning-Mode shots. Do not spend coffee repeating conditions without a specific unresolved question.

## Phase 2 — Baseline dose models

Completed 2026-09-11: the small typed proportional-dose baseline and past-only same-block/exact-setting median-rate comparator, with explicit prospective recommendation records and scoring. See [`dose-control-baseline.md`](dose-control-baseline.md).

Historical metric values documented there are an older staging snapshot; current corrected-source rolling benchmarks are in [historical-analysis.md](historical-analysis.md).

The baselines define the minimum standard that richer grinder-output models must beat.

## Phase 3 — Minimal prospective data-acquisition application

**Implemented 2026-09-14.** The local Streamlit + SQLite application records prospective,
timestamped shots linked to plans frozen before grinding. See [live-workflow.md](live-workflow.md)
for installation, normal use, database location and backups.

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

Initial live setup should make it easy to create/select the current bean **REWE Bio Espresso ganze Bohnen, 1000 g** without hard-coding that bean as a permanent application default.

Delivered: session creation/selection, explicit manual fallback, both existing dose baselines
as frozen candidates with one selected plan, resumable grinding/brewing entry, recent history,
and the original schema version 1 provenance guards. Automated repository and Streamlit workflow
tests cover persistence, chronology, restart and immutable recommendations. Phase 3.1 and its
schema-v2/v3 hardening subsequently extended this persistence model; v1 is no longer the current
live schema. No prospective efficacy claim has been established; live collection and later
evaluation remain necessary.

Grind-setting optimisation remains manual. Learning Mode and Phase 4 have not been implemented.

## Phase 3.1 — Acquisition hardening

Implemented 2026-09-15: schema v2 added transactional v1 migration, explicit phase-recording
timestamps with unknown legacy grinding times preserved, optional bag-open context, immutable
abandonment/invalidation records, reason/confirmation UI, and lifecycle-aware controller
eligibility. Users can release a blocked session without deleting measurements or frozen plans.
No model improvement, retrospective replacement editor, or Learning Mode is included.

A same-day follow-up upgraded the **current live schema to v3** to distinguish frozen intent from
physical grinder execution. `shot_resolutions.no_physical_grinding_confirmed` is persisted only
after explicit confirmation that a pre-grind frozen plan was never executed. Such a confirmed
unexecuted plan remains in the audit trail but is transparent to physical grinder continuity;
invalidated, legacy-ambiguous, or merely missing evidence remains a conservative block boundary.
The v2-to-v3 migration is additive and leaves existing rows `NULL`; fresh databases are created
directly at v3. A narrow dry-run-first maintenance command exists only for the explicitly
identified mistaken pre-grind invalidation and preserves a backup plus original audit metadata.
See [data-model.md](data-model.md), [validation.md](validation.md), and
[live-workflow.md](live-workflow.md) for the authoritative current semantics.

## Phase 4 — Learning / Experiment mode and first designed experiments (not implemented)

Add an explicit experiment intent distinct from normal assisted use. The first version should use transparent Design-of-Experiments principles rather than autonomous Bayesian optimisation.

Experiment families should be selected for concrete identification questions **after checking what the corrected historical dataset already tells us**. Candidate families include:

1. **Repeatability / noise**
   - repeat identical setting + duration only where historical replication is insufficient for the question at hand;
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
   - use the observed pair $(t_{\mathrm{brew}},Y)$ jointly rather than treating $T_{36}^{\mathrm{linear}}$ as truth.

5. **Transition / retention signal**
   - deliberately compare first shot after a setting change with an immediate repeat;
   - repeat enough transitions to determine whether a previous-setting/state term has prospective value.

6. **Drift**
   - revisit a reference condition later in the same bean/session;
   - test whether time/ageing/state changes are large enough to justify recency weighting or a forgetting factor.

Predefine the question, experimental points, replication, and stopping criterion before examining results where practical. Prefer experiments with high expected information gain relative to coffee consumed.

Deliverable: a small prospective dataset with known experimental intent that fills specific gaps left by historical and normal-use data.

See [`research-methods.md`](research-methods.md).

## Phase 5 — Structured system identification / richer models

Add complexity incrementally based on the prospective evidence.

Candidate progression:

1. structured regression for grinder output, including setting effects if demonstrated;
2. recursive least squares / adaptive estimation if online updating is useful;
3. forgetting/recency weighting only if measurable drift exists;
4. robust residual handling where anomalous observations materially affect prediction;
5. learned joint use of $(t_{\mathrm{brew}},Y)$ for extraction;
6. simple previous-setting/change features that do not assume an unvalidated numeric grinder scale;
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
